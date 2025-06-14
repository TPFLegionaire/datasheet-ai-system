#!/usr/bin/env python3
"""
Authentication Module for Datasheet AI Comparison System

This module provides authentication functionality for the web application:
1. User registration and login
2. Password hashing and verification
3. Session management
4. User roles and permissions
5. Integration with the database
6. Support for both internal authentication and OAuth providers
"""

import os
import time
import logging
import hashlib
import secrets
import json
import base64
import hmac
from enum import Enum
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import sqlite3
import re
import uuid
import urllib.parse
import requests
from contextlib import contextmanager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('auth')

# Constants
TOKEN_EXPIRY_DAYS = 7
PASSWORD_MIN_LENGTH = 8
PASSWORD_COMPLEXITY_REGEX = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$'
SESSION_COOKIE_NAME = "datasheet_ai_session"
DEFAULT_ADMIN_EMAIL = "admin@example.com"
DEFAULT_ADMIN_PASSWORD = "Admin@123"  # Should be changed in production

class UserRole(Enum):
    """User role enumeration"""
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"

class AuthProvider(Enum):
    """Authentication provider enumeration"""
    INTERNAL = "internal"
    GOOGLE = "google"
    GITHUB = "github"

@dataclass
class User:
    """User data class"""
    id: int
    email: str
    username: str
    role: UserRole
    provider: AuthProvider
    provider_id: Optional[str] = None
    password_hash: Optional[str] = None
    password_salt: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    last_login: Optional[datetime] = None
    is_active: bool = True
    
    @property
    def is_admin(self) -> bool:
        """Check if user is an admin"""
        return self.role == UserRole.ADMIN
    
    @property
    def is_editor(self) -> bool:
        """Check if user is an editor"""
        return self.role == UserRole.EDITOR or self.role == UserRole.ADMIN
    
    @property
    def is_internal(self) -> bool:
        """Check if user uses internal authentication"""
        return self.provider == AuthProvider.INTERNAL
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "email": self.email,
            "username": self.username,
            "role": self.role.value,
            "provider": self.provider.value,
            "provider_id": self.provider_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "is_active": self.is_active
        }

@dataclass
class Session:
    """Session data class"""
    token: str
    user_id: int
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    
    @property
    def is_expired(self) -> bool:
        """Check if session is expired"""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "token": self.token,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent
        }

class AuthError(Exception):
    """Base authentication error"""
    pass

class RegistrationError(AuthError):
    """Registration error"""
    pass

class LoginError(AuthError):
    """Login error"""
    pass

class SessionError(AuthError):
    """Session error"""
    pass

class PermissionError(AuthError):
    """Permission error"""
    pass

class AuthManager:
    """
    Authentication Manager for Datasheet AI Comparison System
    
    This class provides methods for user authentication, registration,
    session management, and permission checking.
    """
    
    def __init__(self, 
                db_file: str = "datasheet_system.db", 
                secret_key: Optional[str] = None,
                oauth_config: Optional[Dict[str, Any]] = None,
                debug: bool = False):
        """
        Initialize the authentication manager
        
        Args:
            db_file: Path to SQLite database file
            secret_key: Secret key for token signing
            oauth_config: OAuth configuration
            debug: Enable debug mode with additional logging
        """
        self.db_file = db_file
        self.secret_key = secret_key or os.environ.get("AUTH_SECRET_KEY") or self._generate_secret_key()
        self.oauth_config = oauth_config or {}
        self.debug = debug
        
        if debug:
            logger.setLevel(logging.DEBUG)
        
        # Initialize database
        self._init_database()
        
        # Create default admin user if not exists
        self._create_default_admin()
        
        logger.info("Initialized AuthManager")
    
    @contextmanager
    def get_connection(self):
        """
        Context manager for database connections
        
        Yields:
            SQLite connection object
        
        Raises:
            AuthError: If connection fails
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_file)
            conn.row_factory = sqlite3.Row  # Return rows as dictionaries
            yield conn
        except sqlite3.Error as e:
            logger.error(f"Database connection error: {str(e)}")
            raise AuthError(f"Failed to connect to database: {str(e)}")
        finally:
            if conn:
                conn.close()
    
    def _init_database(self):
        """Initialize database schema"""
        try:
            with self.get_connection() as conn:
                c = conn.cursor()
                
                # Create users table
                c.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        email TEXT UNIQUE NOT NULL,
                        username TEXT NOT NULL,
                        role TEXT NOT NULL,
                        provider TEXT NOT NULL,
                        provider_id TEXT,
                        password_hash TEXT,
                        password_salt TEXT,
                        created_at TIMESTAMP NOT NULL,
                        last_login TIMESTAMP,
                        is_active BOOLEAN NOT NULL DEFAULT 1
                    )
                ''')
                
                # Create sessions table
                c.execute('''
                    CREATE TABLE IF NOT EXISTS sessions (
                        token TEXT PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        created_at TIMESTAMP NOT NULL,
                        expires_at TIMESTAMP NOT NULL,
                        ip_address TEXT,
                        user_agent TEXT,
                        FOREIGN KEY (user_id) REFERENCES users (id)
                    )
                ''')
                
                # Create indexes
                c.execute('CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)')
                c.execute('CREATE INDEX IF NOT EXISTS idx_users_provider ON users(provider, provider_id)')
                c.execute('CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)')
                
                conn.commit()
                logger.info("Database schema initialized")
                
        except Exception as e:
            logger.error(f"Database initialization error: {str(e)}")
            raise AuthError(f"Failed to initialize database: {str(e)}")
    
    def _create_default_admin(self):
        """Create default admin user if not exists"""
        try:
            # Check if admin user exists
            with self.get_connection() as conn:
                c = conn.cursor()
                c.execute("SELECT id FROM users WHERE email = ?", (DEFAULT_ADMIN_EMAIL,))
                if c.fetchone():
                    return  # Admin already exists
            
            # Create admin user
            self.register_user(
                email=DEFAULT_ADMIN_EMAIL,
                username="admin",
                password=DEFAULT_ADMIN_PASSWORD,
                role=UserRole.ADMIN
            )
            
            logger.info("Created default admin user")
            
        except Exception as e:
            logger.error(f"Error creating default admin user: {str(e)}")
    
    def _generate_secret_key(self) -> str:
        """Generate a random secret key"""
        return secrets.token_hex(32)
    
    def _hash_password(self, password: str) -> Tuple[str, str]:
        """
        Hash password with a random salt
        
        Args:
            password: Plain text password
            
        Returns:
            Tuple of (password_hash, salt)
        """
        salt = secrets.token_hex(16)
        password_hash = hashlib.pbkdf2_hmac(
            'sha256', 
            password.encode('utf-8'), 
            salt.encode('utf-8'), 
            100000
        ).hex()
        
        return password_hash, salt
    
    def _verify_password(self, password: str, password_hash: str, salt: str) -> bool:
        """
        Verify password against hash
        
        Args:
            password: Plain text password
            password_hash: Stored password hash
            salt: Salt used for hashing
            
        Returns:
            True if password is correct, False otherwise
        """
        computed_hash = hashlib.pbkdf2_hmac(
            'sha256', 
            password.encode('utf-8'), 
            salt.encode('utf-8'), 
            100000
        ).hex()
        
        return secrets.compare_digest(computed_hash, password_hash)
    
    def _generate_session_token(self) -> str:
        """Generate a random session token"""
        return secrets.token_urlsafe(32)
    
    def _sign_token(self, token: str) -> str:
        """
        Sign a token with the secret key
        
        Args:
            token: Token to sign
            
        Returns:
            Signed token
        """
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            token.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return f"{token}.{signature}"
    
    def _verify_token_signature(self, signed_token: str) -> Optional[str]:
        """
        Verify token signature and return the original token
        
        Args:
            signed_token: Signed token
            
        Returns:
            Original token if signature is valid, None otherwise
        """
        try:
            token, signature = signed_token.rsplit('.', 1)
            
            expected_signature = hmac.new(
                self.secret_key.encode('utf-8'),
                token.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            if secrets.compare_digest(signature, expected_signature):
                return token
            
            return None
            
        except Exception:
            return None
    
    def _validate_password_strength(self, password: str) -> bool:
        """
        Validate password strength
        
        Args:
            password: Password to validate
            
        Returns:
            True if password is strong enough, False otherwise
        """
        if len(password) < PASSWORD_MIN_LENGTH:
            return False
        
        # Check for complexity (at least one uppercase, one lowercase, one digit, one special character)
        return bool(re.match(PASSWORD_COMPLEXITY_REGEX, password))
    
    def _validate_email(self, email: str) -> bool:
        """
        Validate email format
        
        Args:
            email: Email to validate
            
        Returns:
            True if email is valid, False otherwise
        """
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(email_regex, email))
    
    def register_user(self, email: str, username: str, password: str, 
                     role: UserRole = UserRole.VIEWER, 
                     provider: AuthProvider = AuthProvider.INTERNAL,
                     provider_id: Optional[str] = None) -> User:
        """
        Register a new user
        
        Args:
            email: User email
            username: Username
            password: Plain text password (for internal auth)
            role: User role
            provider: Authentication provider
            provider_id: Provider-specific ID (for OAuth)
            
        Returns:
            Newly created User object
            
        Raises:
            RegistrationError: If registration fails
        """
        try:
            # Validate email
            if not self._validate_email(email):
                raise RegistrationError("Invalid email format")
            
            # Validate password for internal auth
            if provider == AuthProvider.INTERNAL:
                if not password:
                    raise RegistrationError("Password is required for internal authentication")
                
                if not self._validate_password_strength(password):
                    raise RegistrationError(
                        f"Password must be at least {PASSWORD_MIN_LENGTH} characters long and include "
                        "uppercase, lowercase, digit, and special character"
                    )
            
            # Check if user already exists
            with self.get_connection() as conn:
                c = conn.cursor()
                c.execute("SELECT id FROM users WHERE email = ?", (email,))
                if c.fetchone():
                    raise RegistrationError(f"User with email {email} already exists")
            
            # Hash password for internal auth
            password_hash = None
            password_salt = None
            if provider == AuthProvider.INTERNAL:
                password_hash, password_salt = self._hash_password(password)
            
            # Create user
            with self.get_connection() as conn:
                c = conn.cursor()
                c.execute('''
                    INSERT INTO users 
                    (email, username, role, provider, provider_id, password_hash, password_salt, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    email,
                    username,
                    role.value,
                    provider.value,
                    provider_id,
                    password_hash,
                    password_salt,
                    datetime.now()
                ))
                
                conn.commit()
                user_id = c.lastrowid
            
            # Get created user
            user = self.get_user_by_id(user_id)
            
            logger.info(f"Registered new user: {email} (ID: {user_id}, Role: {role.value})")
            
            return user
            
        except RegistrationError:
            raise
        except Exception as e:
            logger.error(f"Registration error: {str(e)}")
            raise RegistrationError(f"Failed to register user: {str(e)}")
    
    def login_user(self, email: str, password: str, 
                  ip_address: Optional[str] = None,
                  user_agent: Optional[str] = None) -> Tuple[User, Session]:
        """
        Login user with email and password
        
        Args:
            email: User email
            password: Plain text password
            ip_address: Client IP address
            user_agent: Client user agent
            
        Returns:
            Tuple of (User, Session)
            
        Raises:
            LoginError: If login fails
        """
        try:
            # Get user by email
            user = self.get_user_by_email(email)
            
            if not user:
                raise LoginError("Invalid email or password")
            
            if not user.is_active:
                raise LoginError("User account is inactive")
            
            # Check authentication provider
            if user.provider != AuthProvider.INTERNAL:
                raise LoginError(f"Please use {user.provider.value} authentication")
            
            # Verify password
            if not self._verify_password(password, user.password_hash, user.password_salt):
                raise LoginError("Invalid email or password")
            
            # Create session
            session = self.create_session(user.id, ip_address, user_agent)
            
            # Update last login
            with self.get_connection() as conn:
                c = conn.cursor()
                c.execute(
                    "UPDATE users SET last_login = ? WHERE id = ?",
                    (datetime.now(), user.id)
                )
                conn.commit()
            
            logger.info(f"User logged in: {email} (ID: {user.id})")
            
            return user, session
            
        except LoginError:
            raise
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            raise LoginError(f"Failed to login: {str(e)}")
    
    def login_with_oauth(self, provider: AuthProvider, provider_data: Dict[str, Any],
                        ip_address: Optional[str] = None,
                        user_agent: Optional[str] = None) -> Tuple[User, Session]:
        """
        Login or register user with OAuth provider
        
        Args:
            provider: OAuth provider
            provider_data: Provider-specific user data
            ip_address: Client IP address
            user_agent: Client user agent
            
        Returns:
            Tuple of (User, Session)
            
        Raises:
            LoginError: If login fails
        """
        try:
            if provider == AuthProvider.INTERNAL:
                raise LoginError("Cannot use internal provider for OAuth login")
            
            # Extract provider-specific data
            if provider == AuthProvider.GOOGLE:
                provider_id = provider_data.get('sub')
                email = provider_data.get('email')
                username = provider_data.get('name') or email.split('@')[0]
            elif provider == AuthProvider.GITHUB:
                provider_id = str(provider_data.get('id'))
                email = provider_data.get('email')
                username = provider_data.get('login') or email.split('@')[0]
            else:
                raise LoginError(f"Unsupported OAuth provider: {provider.value}")
            
            if not provider_id or not email:
                raise LoginError("Missing required OAuth data")
            
            # Check if user exists
            user = None
            
            # First try by provider ID
            with self.get_connection() as conn:
                c = conn.cursor()
                c.execute(
                    "SELECT * FROM users WHERE provider = ? AND provider_id = ?",
                    (provider.value, provider_id)
                )
                row = c.fetchone()
                
                if row:
                    user = self._row_to_user(row)
            
            # If not found, try by email
            if not user:
                user = self.get_user_by_email(email)
                
                # If user exists but with different provider
                if user and user.provider != provider:
                    raise LoginError(f"Email already registered with {user.provider.value} authentication")
            
            # Register new user if not exists
            if not user:
                user = self.register_user(
                    email=email,
                    username=username,
                    password=None,  # No password for OAuth
                    role=UserRole.VIEWER,  # Default role
                    provider=provider,
                    provider_id=provider_id
                )
            
            # Check if user is active
            if not user.is_active:
                raise LoginError("User account is inactive")
            
            # Create session
            session = self.create_session(user.id, ip_address, user_agent)
            
            # Update last login
            with self.get_connection() as conn:
                c = conn.cursor()
                c.execute(
                    "UPDATE users SET last_login = ? WHERE id = ?",
                    (datetime.now(), user.id)
                )
                conn.commit()
            
            logger.info(f"User logged in with {provider.value}: {email} (ID: {user.id})")
            
            return user, session
            
        except LoginError:
            raise
        except Exception as e:
            logger.error(f"OAuth login error: {str(e)}")
            raise LoginError(f"Failed to login with {provider.value}: {str(e)}")
    
    def create_session(self, user_id: int, 
                      ip_address: Optional[str] = None,
                      user_agent: Optional[str] = None) -> Session:
        """
        Create a new session for a user
        
        Args:
            user_id: User ID
            ip_address: Client IP address
            user_agent: Client user agent
            
        Returns:
            New Session object
            
        Raises:
            SessionError: If session creation fails
        """
        try:
            # Generate token
            token = self._generate_session_token()
            
            # Set expiry date
            expires_at = datetime.now() + timedelta(days=TOKEN_EXPIRY_DAYS)
            
            # Create session
            with self.get_connection() as conn:
                c = conn.cursor()
                c.execute('''
                    INSERT INTO sessions 
                    (token, user_id, created_at, expires_at, ip_address, user_agent)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    token,
                    user_id,
                    datetime.now(),
                    expires_at,
                    ip_address,
                    user_agent
                ))
                
                conn.commit()
            
            # Create Session object
            session = Session(
                token=token,
                user_id=user_id,
                created_at=datetime.now(),
                expires_at=expires_at,
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            logger.debug(f"Created session for user {user_id}")
            
            return session
            
        except Exception as e:
            logger.error(f"Session creation error: {str(e)}")
            raise SessionError(f"Failed to create session: {str(e)}")
    
    def validate_session(self, token: str, 
                        ip_address: Optional[str] = None,
                        user_agent: Optional[str] = None) -> Tuple[User, Session]:
        """
        Validate session token and return user
        
        Args:
            token: Session token
            ip_address: Client IP address
            user_agent: Client user agent
            
        Returns:
            Tuple of (User, Session)
            
        Raises:
            SessionError: If session is invalid or expired
        """
        try:
            # Get session
            with self.get_connection() as conn:
                c = conn.cursor()
                c.execute(
                    "SELECT * FROM sessions WHERE token = ?",
                    (token,)
                )
                session_row = c.fetchone()
                
                if not session_row:
                    raise SessionError("Invalid session token")
            
            # Create Session object
            session = Session(
                token=session_row['token'],
                user_id=session_row['user_id'],
                created_at=datetime.fromisoformat(session_row['created_at']),
                expires_at=datetime.fromisoformat(session_row['expires_at']),
                ip_address=session_row['ip_address'],
                user_agent=session_row['user_agent']
            )
            
            # Check if session is expired
            if session.is_expired:
                # Delete expired session
                self.delete_session(token)
                raise SessionError("Session expired")
            
            # Get user
            user = self.get_user_by_id(session.user_id)
            
            if not user:
                raise SessionError("User not found")
            
            if not user.is_active:
                raise SessionError("User account is inactive")
            
            # Optional: Check IP address and user agent for additional security
            if ip_address and session.ip_address and ip_address != session.ip_address:
                logger.warning(f"IP address mismatch for session {token}: {ip_address} vs {session.ip_address}")
            
            logger.debug(f"Validated session for user {user.id}")
            
            return user, session
            
        except SessionError:
            raise
        except Exception as e:
            logger.error(f"Session validation error: {str(e)}")
            raise SessionError(f"Failed to validate session: {str(e)}")
    
    def delete_session(self, token: str):
        """
        Delete a session
        
        Args:
            token: Session token
        """
        try:
            with self.get_connection() as conn:
                c = conn.cursor()
                c.execute(
                    "DELETE FROM sessions WHERE token = ?",
                    (token,)
                )
                conn.commit()
            
            logger.debug(f"Deleted session {token}")
            
        except Exception as e:
            logger.error(f"Session deletion error: {str(e)}")
    
    def delete_user_sessions(self, user_id: int):
        """
        Delete all sessions for a user
        
        Args:
            user_id: User ID
        """
        try:
            with self.get_connection() as conn:
                c = conn.cursor()
                c.execute(
                    "DELETE FROM sessions WHERE user_id = ?",
                    (user_id,)
                )
                conn.commit()
            
            logger.debug(f"Deleted all sessions for user {user_id}")
            
        except Exception as e:
            logger.error(f"Session deletion error: {str(e)}")
    
    def cleanup_expired_sessions(self):
        """Clean up expired sessions"""
        try:
            with self.get_connection() as conn:
                c = conn.cursor()
                c.execute(
                    "DELETE FROM sessions WHERE expires_at < ?",
                    (datetime.now(),)
                )
                deleted_count = c.rowcount
                conn.commit()
            
            logger.info(f"Cleaned up {deleted_count} expired sessions")
            
        except Exception as e:
            logger.error(f"Session cleanup error: {str(e)}")
    
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """
        Get user by ID
        
        Args:
            user_id: User ID
            
        Returns:
            User object if found, None otherwise
        """
        try:
            with self.get_connection() as conn:
                c = conn.cursor()
                c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
                row = c.fetchone()
                
                if not row:
                    return None
                
                return self._row_to_user(row)
                
        except Exception as e:
            logger.error(f"Error getting user by ID: {str(e)}")
            return None
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """
        Get user by email
        
        Args:
            email: User email
            
        Returns:
            User object if found, None otherwise
        """
        try:
            with self.get_connection() as conn:
                c = conn.cursor()
                c.execute("SELECT * FROM users WHERE email = ?", (email,))
                row = c.fetchone()
                
                if not row:
                    return None
                
                return self._row_to_user(row)
                
        except Exception as e:
            logger.error(f"Error getting user by email: {str(e)}")
            return None
    
    def _row_to_user(self, row: sqlite3.Row) -> User:
        """
        Convert database row to User object
        
        Args:
            row: Database row
            
        Returns:
            User object
        """
        return User(
            id=row['id'],
            email=row['email'],
            username=row['username'],
            role=UserRole(row['role']),
            provider=AuthProvider(row['provider']),
            provider_id=row['provider_id'],
            password_hash=row['password_hash'],
            password_salt=row['password_salt'],
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
            last_login=datetime.fromisoformat(row['last_login']) if row['last_login'] else None,
            is_active=bool(row['is_active'])
        )
    
    def update_user(self, user_id: int, **kwargs) -> User:
        """
        Update user properties
        
        Args:
            user_id: User ID
            **kwargs: Properties to update
            
        Returns:
            Updated User object
            
        Raises:
            AuthError: If update fails
        """
        try:
            # Get current user
            user = self.get_user_by_id(user_id)
            
            if not user:
                raise AuthError(f"User with ID {user_id} not found")
            
            # Prepare update fields
            update_fields = []
            update_values = []
            
            # Process each field
            if 'email' in kwargs:
                email = kwargs['email']
                if not self._validate_email(email):
                    raise AuthError("Invalid email format")
                update_fields.append("email = ?")
                update_values.append(email)
            
            if 'username' in kwargs:
                update_fields.append("username = ?")
                update_values.append(kwargs['username'])
            
            if 'role' in kwargs:
                role = kwargs['role']
                if isinstance(role, str):
                    role = UserRole(role)
                update_fields.append("role = ?")
                update_values.append(role.value)
            
            if 'is_active' in kwargs:
                update_fields.append("is_active = ?")
                update_values.append(1 if kwargs['is_active'] else 0)
            
            if 'password' in kwargs and user.provider == AuthProvider.INTERNAL:
                password = kwargs['password']
                if not self._validate_password_strength(password):
                    raise AuthError(
                        f"Password must be at least {PASSWORD_MIN_LENGTH} characters long and include "
                        "uppercase, lowercase, digit, and special character"
                    )
                
                password_hash, password_salt = self._hash_password(password)
                update_fields.append("password_hash = ?")
                update_values.append(password_hash)
                update_fields.append("password_salt = ?")
                update_values.append(password_salt)
            
            # If no fields to update
            if not update_fields:
                return user
            
            # Add user ID to values
            update_values.append(user_id)
            
            # Update user
            with self.get_connection() as conn:
                c = conn.cursor()
                c.execute(
                    f"UPDATE users SET {', '.join(update_fields)} WHERE id = ?",
                    tuple(update_values)
                )
                conn.commit()
            
            # Get updated user
            updated_user = self.get_user_by_id(user_id)
            
            logger.info(f"Updated user {user_id}")
            
            return updated_user
            
        except AuthError:
            raise
        except Exception as e:
            logger.error(f"User update error: {str(e)}")
            raise AuthError(f"Failed to update user: {str(e)}")
    
    def change_password(self, user_id: int, current_password: str, new_password: str) -> bool:
        """
        Change user password
        
        Args:
            user_id: User ID
            current_password: Current password
            new_password: New password
            
        Returns:
            True if password was changed, False otherwise
            
        Raises:
            AuthError: If password change fails
        """
        try:
            # Get user
            user = self.get_user_by_id(user_id)
            
            if not user:
                raise AuthError(f"User with ID {user_id} not found")
            
            # Check provider
            if user.provider != AuthProvider.INTERNAL:
                raise AuthError(f"Cannot change password for {user.provider.value} authentication")
            
            # Verify current password
            if not self._verify_password(current_password, user.password_hash, user.password_salt):
                raise AuthError("Current password is incorrect")
            
            # Validate new password
            if not self._validate_password_strength(new_password):
                raise AuthError(
                    f"Password must be at least {PASSWORD_MIN_LENGTH} characters long and include "
                    "uppercase, lowercase, digit, and special character"
                )
            
            # Hash new password
            password_hash, password_salt = self._hash_password(new_password)
            
            # Update password
            with self.get_connection() as conn:
                c = conn.cursor()
                c.execute(
                    "UPDATE users SET password_hash = ?, password_salt = ? WHERE id = ?",
                    (password_hash, password_salt, user_id)
                )
                conn.commit()
            
            # Delete all sessions for this user
            self.delete_user_sessions(user_id)
            
            logger.info(f"Changed password for user {user_id}")
            
            return True
            
        except AuthError:
            raise
        except Exception as e:
            logger.error(f"Password change error: {str(e)}")
            raise AuthError(f"Failed to change password: {str(e)}")
    
    def reset_password(self, email: str) -> str:
        """
        Reset user password and return temporary password
        
        Args:
            email: User email
            
        Returns:
            Temporary password
            
        Raises:
            AuthError: If password reset fails
        """
        try:
            # Get user
            user = self.get_user_by_email(email)
            
            if not user:
                raise AuthError(f"User with email {email} not found")
            
            # Check provider
            if user.provider != AuthProvider.INTERNAL:
                raise AuthError(f"Cannot reset password for {user.provider.value} authentication")
            
            # Generate temporary password
            temp_password = self._generate_temporary_password()
            
            # Hash password
            password_hash, password_salt = self._hash_password(temp_password)
            
            # Update password
            with self.get_connection() as conn:
                c = conn.cursor()
                c.execute(
                    "UPDATE users SET password_hash = ?, password_salt = ? WHERE id = ?",
                    (password_hash, password_salt, user.id)
                )
                conn.commit()
            
            # Delete all sessions for this user
            self.delete_user_sessions(user.id)
            
            logger.info(f"Reset password for user {user.id}")
            
            return temp_password
            
        except AuthError:
            raise
        except Exception as e:
            logger.error(f"Password reset error: {str(e)}")
            raise AuthError(f"Failed to reset password: {str(e)}")
    
    def _generate_temporary_password(self) -> str:
        """Generate a temporary password"""
        chars = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        return "".join(secrets.choice(chars) for _ in range(12))
    
    def delete_user(self, user_id: int) -> bool:
        """
        Delete a user
        
        Args:
            user_id: User ID
            
        Returns:
            True if user was deleted, False otherwise
        """
        try:
            # Delete all sessions for this user
            self.delete_user_sessions(user_id)
            
            # Delete user
            with self.get_connection() as conn:
                c = conn.cursor()
                c.execute("DELETE FROM users WHERE id = ?", (user_id,))
                conn.commit()
                
                if c.rowcount == 0:
                    return False
            
            logger.info(f"Deleted user {user_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"User deletion error: {str(e)}")
            return False
    
    def get_all_users(self) -> List[User]:
        """
        Get all users
        
        Returns:
            List of User objects
        """
        try:
            with self.get_connection() as conn:
                c = conn.cursor()
                c.execute("SELECT * FROM users ORDER BY id")
                rows = c.fetchall()
                
                return [self._row_to_user(row) for row in rows]
                
        except Exception as e:
            logger.error(f"Error getting all users: {str(e)}")
            return []
    
    def check_permission(self, user_id: int, required_role: UserRole) -> bool:
        """
        Check if user has required role
        
        Args:
            user_id: User ID
            required_role: Required role
            
        Returns:
            True if user has required role, False otherwise
        """
        try:
            # Get user
            user = self.get_user_by_id(user_id)
            
            if not user:
                return False
            
            if not user.is_active:
                return False
            
            # Admin has all permissions
            if user.role == UserRole.ADMIN:
                return True
            
            # Editor has editor and viewer permissions
            if user.role == UserRole.EDITOR and required_role == UserRole.VIEWER:
                return True
            
            # Otherwise, check exact role match
            return user.role == required_role
            
        except Exception as e:
            logger.error(f"Permission check error: {str(e)}")
            return False
    
    def require_permission(self, user_id: int, required_role: UserRole):
        """
        Require user to have a specific role
        
        Args:
            user_id: User ID
            required_role: Required role
            
        Raises:
            PermissionError: If user doesn't have required role
        """
        if not self.check_permission(user_id, required_role):
            raise PermissionError(f"User {user_id} doesn't have required role: {required_role.value}")
    
    # OAuth helpers
    def get_oauth_url(self, provider: AuthProvider, redirect_uri: str) -> str:
        """
        Get OAuth authorization URL
        
        Args:
            provider: OAuth provider
            redirect_uri: Redirect URI after authorization
            
        Returns:
            Authorization URL
            
        Raises:
            AuthError: If provider is not supported
        """
        try:
            if provider == AuthProvider.GOOGLE:
                return self._get_google_auth_url(redirect_uri)
            elif provider == AuthProvider.GITHUB:
                return self._get_github_auth_url(redirect_uri)
            else:
                raise AuthError(f"Unsupported OAuth provider: {provider.value}")
                
        except AuthError:
            raise
        except Exception as e:
            logger.error(f"OAuth URL generation error: {str(e)}")
            raise AuthError(f"Failed to generate OAuth URL: {str(e)}")
    
    def _get_google_auth_url(self, redirect_uri: str) -> str:
        """
        Get Google OAuth authorization URL
        
        Args:
            redirect_uri: Redirect URI after authorization
            
        Returns:
            Authorization URL
        """
        client_id = self.oauth_config.get('google', {}).get('client_id')
        
        if not client_id:
            raise AuthError("Google OAuth client ID not configured")
        
        params = {
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'scope': 'email profile',
            'response_type': 'code',
            'access_type': 'offline',
            'state': self._generate_oauth_state()
        }
        
        return f"https://accounts.google.com/o/oauth2/auth?{urllib.parse.urlencode(params)}"
    
    def _get_github_auth_url(self, redirect_uri: str) -> str:
        """
        Get GitHub OAuth authorization URL
        
        Args:
            redirect_uri: Redirect URI after authorization
            
        Returns:
            Authorization URL
        """
        client_id = self.oauth_config.get('github', {}).get('client_id')
        
        if not client_id:
            raise AuthError("GitHub OAuth client ID not configured")
        
        params = {
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'scope': 'user:email',
            'state': self._generate_oauth_state()
        }
        
        return f"https://github.com/login/oauth/authorize?{urllib.parse.urlencode(params)}"
    
    def _generate_oauth_state(self) -> str:
        """Generate OAuth state parameter"""
        return secrets.token_urlsafe(16)
    
    def exchange_oauth_code(self, provider: AuthProvider, code: str, redirect_uri: str) -> Dict[str, Any]:
        """
        Exchange OAuth code for user data
        
        Args:
            provider: OAuth provider
            code: Authorization code
            redirect_uri: Redirect URI
            
        Returns:
            User data from provider
            
        Raises:
            AuthError: If exchange fails
        """
        try:
            if provider == AuthProvider.GOOGLE:
                return self._exchange_google_code(code, redirect_uri)
            elif provider == AuthProvider.GITHUB:
                return self._exchange_github_code(code, redirect_uri)
            else:
                raise AuthError(f"Unsupported OAuth provider: {provider.value}")
                
        except AuthError:
            raise
        except Exception as e:
            logger.error(f"OAuth code exchange error: {str(e)}")
            raise AuthError(f"Failed to exchange OAuth code: {str(e)}")
    
    def _exchange_google_code(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """
        Exchange Google OAuth code for user data
        
        Args:
            code: Authorization code
            redirect_uri: Redirect URI
            
        Returns:
            User data from Google
        """
        client_id = self.oauth_config.get('google', {}).get('client_id')
        client_secret = self.oauth_config.get('google', {}).get('client_secret')
        
        if not client_id or not client_secret:
            raise AuthError("Google OAuth credentials not configured")
        
        # Exchange code for token
        token_url = "https://oauth2.googleapis.com/token"
        token_data = {
            'code': code,
            'client_id': client_id,
            'client_secret': client_secret,
            'redirect_uri': redirect_uri,
            'grant_type': 'authorization_code'
        }
        
        token_response = requests.post(token_url, data=token_data)
        
        if token_response.status_code != 200:
            raise AuthError(f"Failed to exchange Google code: {token_response.text}")
        
        token_json = token_response.json()
        access_token = token_json.get('access_token')
        
        if not access_token:
            raise AuthError("No access token in Google response")
        
        # Get user info
        userinfo_url = "https://www.googleapis.com/oauth2/v3/userinfo"
        headers = {'Authorization': f"Bearer {access_token}"}
        
        userinfo_response = requests.get(userinfo_url, headers=headers)
        
        if userinfo_response.status_code != 200:
            raise AuthError(f"Failed to get Google user info: {userinfo_response.text}")
        
        return userinfo_response.json()
    
    def _exchange_github_code(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """
        Exchange GitHub OAuth code for user data
        
        Args:
            code: Authorization code
            redirect_uri: Redirect URI
            
        Returns:
            User data from GitHub
        """
        client_id = self.oauth_config.get('github', {}).get('client_id')
        client_secret = self.oauth_config.get('github', {}).get('client_secret')
        
        if not client_id or not client_secret:
            raise AuthError("GitHub OAuth credentials not configured")
        
        # Exchange code for token
        token_url = "https://github.com/login/oauth/access_token"
        token_data = {
            'code': code,
            'client_id': client_id,
            'client_secret': client_secret,
            'redirect_uri': redirect_uri
        }
        headers = {'Accept': 'application/json'}
        
        token_response = requests.post(token_url, data=token_data, headers=headers)
        
        if token_response.status_code != 200:
            raise AuthError(f"Failed to exchange GitHub code: {token_response.text}")
        
        token_json = token_response.json()
        access_token = token_json.get('access_token')
        
        if not access_token:
            raise AuthError("No access token in GitHub response")
        
        # Get user info
        userinfo_url = "https://api.github.com/user"
        headers = {
            'Authorization': f"token {access_token}",
            'Accept': 'application/json'
        }
        
        userinfo_response = requests.get(userinfo_url, headers=headers)
        
        if userinfo_response.status_code != 200:
            raise AuthError(f"Failed to get GitHub user info: {userinfo_response.text}")
        
        user_data = userinfo_response.json()
        
        # Get email if not included in user data
        if not user_data.get('email'):
            email_url = "https://api.github.com/user/emails"
            email_response = requests.get(email_url, headers=headers)
            
            if email_response.status_code == 200:
                emails = email_response.json()
                primary_email = next((e for e in emails if e.get('primary')), None)
                
                if primary_email:
                    user_data['email'] = primary_email.get('email')
        
        return user_data


# Streamlit integration helpers
def streamlit_auth_callback(auth_manager: AuthManager):
    """
    Create a callback for Streamlit authentication
    
    Args:
        auth_manager: AuthManager instance
        
    Returns:
        Authentication callback function for Streamlit
    """
    import streamlit as st
    
    def authenticate():
        """
        Authenticate user in Streamlit
        
        Returns:
            User object if authenticated, None otherwise
        """
        # Check for existing session
        if SESSION_COOKIE_NAME in st.session_state:
            try:
                token = st.session_state[SESSION_COOKIE_NAME]
                user, session = auth_manager.validate_session(token)
                return user
            except SessionError:
                # Clear invalid session
                del st.session_state[SESSION_COOKIE_NAME]
                return None
        
        return None
    
    def login(email: str, password: str) -> bool:
        """
        Login user in Streamlit
        
        Args:
            email: User email
            password: User password
            
        Returns:
            True if login successful, False otherwise
        """
        try:
            user, session = auth_manager.login_user(
                email=email,
                password=password,
                ip_address=None,  # Could get from Streamlit if needed
                user_agent=None   # Could get from Streamlit if needed
            )
            
            # Store session token
            st.session_state[SESSION_COOKIE_NAME] = session.token
            
            return True
            
        except LoginError as e:
            st.error(str(e))
            return False
    
    def logout():
        """Logout user in Streamlit"""
        if SESSION_COOKIE_NAME in st.session_state:
            # Delete session from database
            try:
                auth_manager.delete_session(st.session_state[SESSION_COOKIE_NAME])
            except:
                pass
            
            # Clear session from state
            del st.session_state[SESSION_COOKIE_NAME]
    
    def require_auth(role: UserRole = UserRole.VIEWER):
        """
        Require authentication with specific role
        
        Args:
            role: Required role
            
        Returns:
            User object if authenticated with required role
            
        Raises:
            SystemExit: If not authenticated or insufficient role
        """
        user = authenticate()
        
        if not user:
            st.error("Please log in to access this page")
            
            # Show login form
            with st.form("login_form"):
                email = st.text_input("Email")
                password = st.text_input("Password", type="password")
                submit = st.form_submit_button("Login")
                
                if submit:
                    login(email, password)
                    st.experimental_rerun()
            
            # Stop execution
            st.stop()
        
        # Check role
        if not auth_manager.check_permission(user.id, role):
            st.error(f"You don't have the required role: {role.value}")
            st.stop()
        
        return user
    
    # Return functions
    return {
        "authenticate": authenticate,
        "login": login,
        "logout": logout,
        "require_auth": require_auth
    }


# Example usage
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Auth Manager CLI")
    parser.add_argument("--create-user", action="store_true", help="Create a user")
    parser.add_argument("--email", help="User email")
    parser.add_argument("--username", help="Username")
    parser.add_argument("--password", help="User password")
    parser.add_argument("--role", choices=["admin", "editor", "viewer"], default="viewer", help="User role")
    parser.add_argument("--list-users", action="store_true", help="List all users")
    parser.add_argument("--cleanup", action="store_true", help="Clean up expired sessions")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()
    
    # Initialize auth manager
    auth_manager = AuthManager(debug=args.debug)
    
    try:
        if args.create_user:
            if not args.email or not args.username or not args.password:
                print("Error: Email, username, and password are required")
                exit(1)
            
            user = auth_manager.register_user(
                email=args.email,
                username=args.username,
                password=args.password,
                role=UserRole(args.role)
            )
            
            print(f"User created: {user.email} (ID: {user.id}, Role: {user.role.value})")
        
        elif args.list_users:
            users = auth_manager.get_all_users()
            
            print(f"Total users: {len(users)}")
            print("-" * 80)
            print(f"{'ID':<5} {'Email':<30} {'Username':<20} {'Role':<10} {'Provider':<10} {'Active':<6}")
            print("-" * 80)
            
            for user in users:
                print(f"{user.id:<5} {user.email:<30} {user.username:<20} {user.role.value:<10} {user.provider.value:<10} {'Yes' if user.is_active else 'No':<6}")
        
        elif args.cleanup:
            auth_manager.cleanup_expired_sessions()
        
        else:
            parser.print_help()
            
    except Exception as e:
        print(f"Error: {str(e)}")
        exit(1)
