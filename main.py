#!/usr/bin/env python3
"""
AI-Powered Telegram Bot for Smart Website Monitoring
Production-ready version with comprehensive error handling, documentation, and testing.

Features:
- AI-powered notification filtering
- Personalized user experiences
- Asynchronous monitoring
- Comprehensive error handling
- Professional logging

Author: AI Assistant
Version: 3.2.0 (Security Fixed Version)
License: MIT
"""

import logging
import asyncio
import hashlib
import random
import secrets
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Set, Optional, Any, Union
import os
import sys
import re
from dataclasses import dataclass

# Load environment variables safely
from dotenv import load_dotenv

load_dotenv()


# Configuration with proper validation
class Config:
    """Application configuration constants with validation"""

    @classmethod
    def validate_config(cls):
        """Validate all configuration values"""
        errors = []

        # Validate BOT_TOKEN
        cls.BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
        if not cls.BOT_TOKEN:
            errors.append("TELEGRAM_BOT_TOKEN environment variable is not set")
        elif not cls._validate_bot_token(cls.BOT_TOKEN):
            errors.append("TELEGRAM_BOT_TOKEN has invalid format")

        # Validate numeric configurations
        numeric_configs = {
            'MAX_BEHAVIOR_HISTORY': cls.MAX_BEHAVIOR_HISTORY,
            'MONITORING_INTERVAL_SECONDS': cls.MONITORING_INTERVAL_SECONDS,
            'NOTIFICATION_GROUPING_TIMEOUT_SECONDS': cls.NOTIFICATION_GROUPING_TIMEOUT_SECONDS,
            'MAX_RETRY_ATTEMPTS': cls.MAX_RETRY_ATTEMPTS,
            'MAX_URLS_PER_USER': cls.MAX_URLS_PER_USER,
            'MAX_MESSAGE_LENGTH': cls.MAX_MESSAGE_LENGTH,
            'REQUEST_TIMEOUT': cls.REQUEST_TIMEOUT
        }

        for name, value in numeric_configs.items():
            if not isinstance(value, (int, float)) or value <= 0:
                errors.append(f"{name} must be a positive number, got {value}")

        # Validate INITIAL_IMPORTANCE_THRESHOLD
        if not 0 <= cls.INITIAL_IMPORTANCE_THRESHOLD <= 1:
            errors.append(
                f"INITIAL_IMPORTANCE_THRESHOLD must be between 0 and 1, got {cls.INITIAL_IMPORTANCE_THRESHOLD}")

        if errors:
            raise ConfigurationError(f"Configuration validation failed:\n" + "\n".join(errors))

    @staticmethod
    def _validate_bot_token(token: str) -> bool:
        """Validate Telegram bot token format"""
        if not token:
            return False
        # Telegram bot token format: 1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ
        pattern = r'^\d{9,10}:[a-zA-Z0-9_-]{35}$'
        return bool(re.match(pattern, token))

    # Configuration constants
    BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
    MAX_BEHAVIOR_HISTORY = 200
    MONITORING_INTERVAL_SECONDS = 30
    NOTIFICATION_GROUPING_TIMEOUT_SECONDS = 300
    MAX_RETRY_ATTEMPTS = 3
    INITIAL_IMPORTANCE_THRESHOLD = 0.6
    MAX_URLS_PER_USER = 50
    MAX_MESSAGE_LENGTH = 4096
    REQUEST_TIMEOUT = 30


# Configure structured logging with safe formatter
class SafeFormatter(logging.Formatter):
    """Formatter that masks sensitive data in logs"""

    def __init__(self, fmt=None, datefmt=None, style='%'):
        super().__init__(fmt, datefmt, style)
        # Pattern to match bot tokens
        self.token_pattern = re.compile(r'\b\d{9,10}:[a-zA-Z0-9_-]{35}\b')

    def format(self, record):
        message = super().format(record)
        # Mask bot tokens
        message = self.token_pattern.sub('[BOT_TOKEN_MASKED]', message)
        return message


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('website_monitor.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

# Apply safe formatter to all handlers
for handler in logging.getLogger().handlers:
    handler.setFormatter(SafeFormatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))

logger = logging.getLogger(__name__)

# Import external dependencies with comprehensive error handling
try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
    from telegram.error import TelegramError, NetworkError, RetryAfter
except ImportError as e:
    logger.critical(f"Failed to import required Telegram libraries: {e}")
    logger.critical("Please install: pip install python-telegram-bot==20.7 python-dotenv")
    sys.exit(1)


class MonitoringError(Exception):
    """Base exception for monitoring-related errors"""
    pass


class ConfigurationError(MonitoringError):
    """Configuration-related errors"""
    pass


class NotificationError(MonitoringError):
    """Notification delivery errors"""
    pass


class ValidationError(MonitoringError):
    """Data validation errors"""
    pass


class NotificationType(Enum):
    """Types of notifications with user-friendly descriptions and priority levels"""
    INFO = ("ℹ️ Информация", 1)
    WARNING = ("⚠️ Предупреждение", 3)
    ERROR = ("🚨 Ошибка", 4)
    SUCCESS = ("✅ Успех", 2)
    UPDATE = ("🔄 Обновление", 2)
    CRITICAL = ("🔴 Критическое", 5)

    def __init__(self, description: str, priority: int):
        self.description = description
        self.priority = priority

    @property
    def value(self) -> str:
        return self.description


class ChangeCategory(Enum):
    """Categories of website changes"""
    CONTENT = "📝 Контент"
    PERFORMANCE = "⚡ Производительность"
    AVAILABILITY = "🌐 Доступность"
    SECURITY = "🔒 Безопасность"
    STRUCTURE = "🏗️ Структура"
    SEO = "🔍 SEO"


class UserReaction(Enum):
    """User feedback reactions for AI learning"""
    LIKE = "like"
    DISLIKE = "dislike"
    IGNORE = "ignore"


@dataclass
class ChangeDetectionResult:
    """Structured result of website change detection"""
    changes: List[Dict[str, Any]]
    check_timestamp: datetime
    website_status: int
    response_time: int
    success: bool
    error_message: Optional[str] = None


class URLValidator:
    """URL validation utility class"""

    @staticmethod
    def validate_url(url: str) -> bool:
        """
        Validate URL format and safety

        Args:
            url: URL to validate

        Returns:
            True if URL is valid and safe

        Raises:
            ValidationError: If URL is invalid or unsafe
        """
        if not url:
            raise ValidationError("URL cannot be empty")

        # Basic URL format validation
        url_pattern = re.compile(
            r'^(https?://)'  # http:// or https://
            r'([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}'  # domain
            r'(:[0-9]+)?'  # optional port
            r'(/.*)?$'  # optional path
        )

        if not url_pattern.match(url):
            raise ValidationError(f"Invalid URL format: {url}")

        # Security checks
        if URLValidator._contains_suspicious_patterns(url):
            raise ValidationError(f"URL contains suspicious patterns: {url}")

        return True

    @staticmethod
    def _contains_suspicious_patterns(url: str) -> bool:
        """Check for potentially malicious URL patterns"""
        suspicious_patterns = [
            r'\.\./',  # Directory traversal
            r'\.\.\\',  # Windows directory traversal
            r'javascript:',  # JavaScript injection
            r'vbscript:',  # VBScript injection
            r'data:',  # Data URI
            r'file:',  # File protocol
        ]

        return any(re.search(pattern, url, re.IGNORECASE) for pattern in suspicious_patterns)

    @staticmethod
    def normalize_url(url: str) -> str:
        """Normalize URL by adding protocol if missing"""
        if not url.startswith(('http://', 'https://')):
            return f'https://{url}'
        return url


class AINotificationFilter:
    """
    AI-powered notification filtering and personalization system.
    """

    def __init__(self):
        self.user_profiles: Dict[int, Dict[str, Any]] = {}
        self.user_behavior: Dict[int, List[Dict[str, Any]]] = {}
        self.notification_feedback: Dict[str, Dict[str, Any]] = {}
        self.user_notification_history: Dict[int, List[Dict[str, Any]]] = {}

        # Weights for different notification types based on severity
        self._type_weights = {
            NotificationType.CRITICAL: 1.0,
            NotificationType.ERROR: 0.9,
            NotificationType.WARNING: 0.7,
            NotificationType.SUCCESS: 0.6,
            NotificationType.UPDATE: 0.5,
            NotificationType.INFO: 0.3
        }

        # AI recommendations database
        self._recommendations = self._initialize_recommendations()

        logger.info("AI Notification Filter initialized successfully")

    def _initialize_recommendations(self) -> Dict[Union[NotificationType, ChangeCategory], List[str]]:
        """
        Initialize AI recommendation database with contextual advice.
        """
        return {
            NotificationType.ERROR: [
                "Рекомендуем немедленно проверить доступность сайта",
                "Возможны проблемы с хостингом или DNS - проверьте настройки",
                "Проверьте SSL сертификат и настройки сервера"
            ],
            NotificationType.WARNING: [
                "Следите за дальнейшими изменениями в течение часа",
                "Рекомендуем настроить более частые проверки для этого сайта",
                "Возможно, требуется оптимизация сайта или обновление контента"
            ],
            NotificationType.CRITICAL: [
                "Критическая ситуация! Требуется немедленное вмешательство",
                "Рекомендуем проверить все системы мониторинга и резервные копии",
                "Возможна атака или серьезный сбой - проверьте логи сервера"
            ],
            NotificationType.UPDATE: [
                "Контент был обновлен - проверьте актуальность информации",
                "Рекомендуем проанализировать изменения на предмет SEO-оптимизации",
                "Возможно, это плановое обновление - сверьтесь с расписанием"
            ],
            ChangeCategory.PERFORMANCE: [
                "Рекомендуем оптимизировать скорость загрузки и кэширование",
                "Проверьте CDN настройки и сжатие ресурсов",
                "Возможно, требуется обновление серверного оборудования"
            ],
            ChangeCategory.SECURITY: [
                "Рекомендуем проверить безопасность сайта и обновить SSL",
                "Обновите пароли и проверьте права доступа",
                "Проверьте логи на предмет подозрительной активности"
            ]
        }

    def analyze_user_behavior(self, user_id: int, action: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Analyze and record user behavior for personalization and AI learning.
        """
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValidationError(f"Invalid user ID: {user_id}")

        if not action or not isinstance(action, str):
            raise ValidationError("Action must be a non-empty string")

        try:
            if user_id not in self.user_behavior:
                self.user_behavior[user_id] = []

            behavior_entry = {
                'action': action,
                'timestamp': datetime.now(),
                'metadata': metadata or {}
            }

            self.user_behavior[user_id].append(behavior_entry)
            self._trim_behavior_history(user_id)

            logger.debug(f"Recorded behavior for user {user_id}: {action}")

        except Exception as e:
            logger.error(f"Error analyzing user behavior for user {user_id}: {e}")
            raise MonitoringError(f"Failed to analyze user behavior: {e}")

    def _trim_behavior_history(self, user_id: int) -> None:
        """Keep only recent behavior history to manage memory usage."""
        try:
            if user_id in self.user_behavior:
                if len(self.user_behavior[user_id]) > Config.MAX_BEHAVIOR_HISTORY:
                    self.user_behavior[user_id] = self.user_behavior[user_id][-Config.MAX_BEHAVIOR_HISTORY:]
        except Exception as e:
            logger.warning(f"Error trimming behavior history for user {user_id}: {e}")

    def record_notification_feedback(self, notification_id: str, user_id: int, reaction: UserReaction) -> None:
        """
        Record user feedback on notifications for AI learning and personalization.
        """
        if not notification_id:
            raise ValidationError("Notification ID cannot be empty")

        if not isinstance(user_id, int) or user_id <= 0:
            raise ValidationError(f"Invalid user ID: {user_id}")

        if not isinstance(reaction, UserReaction):
            raise ValidationError("Reaction must be a valid UserReaction enum value")

        try:
            self.notification_feedback[notification_id] = {
                'user_id': user_id,
                'reaction': reaction,
                'timestamp': datetime.now()
            }

            self._update_user_preferences(user_id, reaction)
            logger.info(f"Recorded feedback for notification {notification_id}: {reaction.value}")

        except Exception as e:
            logger.error(f"Error recording feedback for notification {notification_id}: {e}")
            raise MonitoringError(f"Failed to record notification feedback: {e}")

    def _update_user_preferences(self, user_id: int, reaction: UserReaction) -> None:
        """
        Update user preferences based on feedback using reinforcement learning.
        """
        try:
            profile = self.get_user_preferences(user_id)
            stats = profile['reaction_stats']

            # Update reaction statistics and adjust sensitivity
            if reaction == UserReaction.LIKE:
                stats['likes'] += 1
                # Increase sensitivity (lower threshold) for liked content
                profile['importance_threshold'] = max(0.1, profile['importance_threshold'] - 0.05)
                logger.debug(f"Increased sensitivity for user {user_id}")

            elif reaction == UserReaction.DISLIKE:
                stats['dislikes'] += 1
                # Decrease sensitivity (higher threshold) for disliked content
                profile['importance_threshold'] = min(0.95, profile['importance_threshold'] + 0.05)
                logger.debug(f"Decreased sensitivity for user {user_id}")

            else:  # IGNORE
                stats['ignores'] += 1
                # Small adjustment for ignored content
                profile['importance_threshold'] = min(0.9, profile['importance_threshold'] + 0.02)

        except Exception as e:
            logger.error(f"Error updating preferences for user {user_id}: {e}")

    def calculate_change_importance(self, user_id: int, change_data: Dict[str, Any]) -> float:
        """
        Calculate importance score for a change using multi-factor AI analysis.
        """
        try:
            profile = self.get_user_preferences(user_id)

            importance_factors = [
                self._calculate_type_importance(change_data),
                self._calculate_category_importance(change_data, profile),
                self._calculate_time_importance(),
                self._calculate_reaction_importance(profile),
                self._calculate_frequency_importance(user_id)
            ]

            final_importance = sum(importance_factors)
            normalized_importance = max(0.1, min(1.0, final_importance))

            logger.debug(f"Calculated importance {normalized_importance:.2f} for user {user_id}")
            return normalized_importance

        except Exception as e:
            logger.error(f"Error calculating importance for user {user_id}: {e}")
            return 0.5

    def _calculate_type_importance(self, change_data: Dict[str, Any]) -> float:
        """Calculate importance based on notification type severity."""
        try:
            change_type = change_data.get('type')
            return self._type_weights.get(change_type, 0.5)
        except Exception as e:
            logger.warning(f"Error calculating type importance: {e}")
            return 0.5

    def _calculate_category_importance(self, change_data: Dict[str, Any], profile: Dict[str, Any]) -> float:
        """Calculate importance based on user's preferred categories."""
        try:
            category = change_data.get('category')
            if category and category in profile.get('preferred_categories', []):
                return 0.2
            return 0.0
        except Exception as e:
            logger.warning(f"Error calculating category importance: {e}")
            return 0.0

    def _calculate_time_importance(self) -> float:
        """Calculate importance based on time of day (working hours preference)."""
        try:
            current_hour = datetime.now().hour
            # Prefer working hours (9 AM to 6 PM)
            return 0.1 if 9 <= current_hour <= 18 else -0.1
        except Exception as e:
            logger.warning(f"Error calculating time importance: {e}")
            return 0.0

    def _calculate_reaction_importance(self, profile: Dict[str, Any]) -> float:
        """Calculate importance based on user's historical reactions."""
        try:
            stats = profile['reaction_stats']
            total_reactions = sum(stats.values())

            if total_reactions > 0:
                like_ratio = stats['likes'] / total_reactions
                # Adjust based on whether user generally likes notifications
                return (like_ratio - 0.5) * 0.3
            return 0.0
        except Exception as e:
            logger.warning(f"Error calculating reaction importance: {e}")
            return 0.0

    def _calculate_frequency_importance(self, user_id: int) -> float:
        """Calculate importance based on change frequency (rarer changes are more important)."""
        try:
            if user_id not in self.user_notification_history:
                return 0.0

            recent_changes = [
                change for change in self.user_notification_history[user_id]
                if change['timestamp'] > datetime.now() - timedelta(hours=24)
            ]

            # Penalize if too many changes recently (notification fatigue)
            return -0.1 if len(recent_changes) > 10 else 0.0
        except Exception as e:
            logger.warning(f"Error calculating frequency importance: {e}")
            return 0.0

    def should_send_notification(self, user_id: int, change_data: Dict[str, Any]) -> bool:
        """
        Determine if notification should be sent based on AI analysis.
        """
        try:
            importance = self.calculate_change_importance(user_id, change_data)
            profile = self.get_user_preferences(user_id)
            threshold = profile.get('importance_threshold', Config.INITIAL_IMPORTANCE_THRESHOLD)

            should_send = importance >= threshold

            if should_send:
                logger.debug(
                    f"Approving notification for user {user_id} (importance: {importance:.2f} >= {threshold:.2f})")
            else:
                logger.debug(
                    f"Filtering notification for user {user_id} (importance: {importance:.2f} < {threshold:.2f})")

            return should_send

        except Exception as e:
            logger.error(f"Error determining notification send for user {user_id}: {e}")
            return True

    def get_user_preferences(self, user_id: int) -> Dict[str, Any]:
        """
        Get or create user preferences profile.
        """
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValidationError(f"Invalid user ID: {user_id}")

        if user_id not in self.user_profiles:
            self.user_profiles[user_id] = self._create_default_user_profile()
            logger.info(f"Created default profile for new user {user_id}")

        return self.user_profiles[user_id]

    def _create_default_user_profile(self) -> Dict[str, Any]:
        """Create default user profile with intelligent initial settings."""
        current_hour = datetime.now().hour
        sensitivity = 'low' if current_hour < 9 or current_hour > 22 else 'medium'

        return {
            'preferred_categories': [ChangeCategory.AVAILABILITY, ChangeCategory.SECURITY],
            'sensitivity': sensitivity,
            'importance_threshold': Config.INITIAL_IMPORTANCE_THRESHOLD,
            'learning_rate': 0.1,
            'reaction_stats': {'likes': 0, 'dislikes': 0, 'ignores': 0},
            'active_hours': list(range(9, 22)),
            'notification_style': 'detailed',
            'created_at': datetime.now(),
            'last_updated': datetime.now()
        }

    def group_related_notifications(self, user_id: int, notifications: List[Dict[str, Any]]) -> List[
        List[Dict[str, Any]]]:
        """
        Group related notifications to reduce spam and improve user experience.
        """
        try:
            if not notifications:
                return []

            groups = []
            processed_ids = set()

            for notification in notifications:
                if notification['id'] in processed_ids:
                    continue

                related_group = self._find_related_notifications(notification, notifications, processed_ids)
                groups.append(related_group)

            logger.debug(f"Grouped {len(notifications)} notifications into {len(groups)} groups for user {user_id}")
            return groups

        except Exception as e:
            logger.error(f"Error grouping notifications for user {user_id}: {e}")
            return [[notification] for notification in notifications]

    def _find_related_notifications(self, base_notification: Dict[str, Any],
                                    all_notifications: List[Dict[str, Any]],
                                    processed_ids: Set[str]) -> List[Dict[str, Any]]:
        """Find notifications related to the base notification."""
        related = [base_notification]
        processed_ids.add(base_notification['id'])

        for other_notification in all_notifications:
            if other_notification['id'] in processed_ids:
                continue

            if self._are_notifications_related(base_notification, other_notification):
                related.append(other_notification)
                processed_ids.add(other_notification['id'])

        return related

    def _are_notifications_related(self, notification1: Dict[str, Any], notification2: Dict[str, Any]) -> bool:
        """Check if two notifications are related based on URL and timing."""
        try:
            time_diff = abs((notification1['timestamp'] - notification2['timestamp']).total_seconds())
            same_url = notification1['url'] == notification2['url']

            return same_url and time_diff < Config.NOTIFICATION_GROUPING_TIMEOUT_SECONDS
        except Exception as e:
            logger.warning(f"Error checking notification relation: {e}")
            return False

    def generate_personalized_message(self, user_id: int, change_data: Dict[str, Any]) -> str:
        """
        Generate personalized notification message based on user preferences.
        """
        try:
            profile = self.get_user_preferences(user_id)
            importance = self.calculate_change_importance(user_id, change_data)
            style = profile.get('notification_style', 'detailed')

            if style == 'brief':
                message = self._generate_brief_message(change_data, importance)
            else:
                message = self._generate_detailed_message(change_data, importance, profile)

            # Ensure message length is within Telegram limits
            if len(message) > Config.MAX_MESSAGE_LENGTH:
                message = message[:Config.MAX_MESSAGE_LENGTH - 100] + "\n\n... (сообщение сокращено)"

            logger.debug(f"Generated {style} message for user {user_id}")
            return message

        except Exception as e:
            logger.error(f"Error generating message for user {user_id}: {e}")
            return f"{change_data.get('type', NotificationType.INFO).value}: {change_data.get('description', 'Изменение на сайте')}"

    def _generate_brief_message(self, change_data: Dict[str, Any], importance: float) -> str:
        """Generate brief notification message."""
        priority_emoji = self._get_priority_emoji(importance)
        return f"{priority_emoji} {change_data['type'].value}: {change_data['description']}"

    def _generate_detailed_message(self, change_data: Dict[str, Any], importance: float,
                                   profile: Dict[str, Any]) -> str:
        """Generate detailed personalized notification message."""
        message_parts = [
            f"{change_data['type'].value}",
            f"{self._get_priority_indicator(importance)}",
            f"📋 {change_data['description']}",
            f"🌐 Сайт: {change_data['url']}"
        ]

        if 'category' in change_data:
            message_parts.append(f"📂 Категория: {change_data['category'].value}")

        # Personalization based on user preferences
        if self._is_preferred_category(change_data, profile):
            message_parts.append("⭐ **Это важно для вас!**")

        # AI recommendations
        recommendation = self._generate_ai_recommendation(change_data, importance)
        if recommendation:
            message_parts.append(f"💡 **Рекомендация AI:** {recommendation}")

        # Contextual information
        context_message = self._get_context_message(importance)
        if context_message:
            message_parts.append(context_message)

        return "\n".join(message_parts)

    def _get_priority_emoji(self, importance: float) -> str:
        """Get emoji based on importance level."""
        if importance > 0.8:
            return "🔴"
        elif importance > 0.5:
            return "🟡"
        else:
            return "🟢"

    def _get_priority_indicator(self, importance: float) -> str:
        """Get priority indicator text based on importance."""
        if importance > 0.8:
            return "🔴 **ВЫСОКАЯ ВАЖНОСТЬ**"
        elif importance > 0.6:
            return "🟡 **СРЕДНЯЯ ВАЖНОСТЬ**"
        else:
            return "🟢 **НИЗКАЯ ВАЖНОСТЬ**"

    def _is_preferred_category(self, change_data: Dict[str, Any], profile: Dict[str, Any]) -> bool:
        """Check if change category is in user's preferred categories."""
        try:
            category = change_data.get('category')
            return category and category in profile.get('preferred_categories', [])
        except Exception:
            return False

    def _get_context_message(self, importance: float) -> str:
        """Get contextual message based on importance."""
        if importance < 0.4:
            return "\n💤 Это информационное сообщение"
        elif importance > 0.8:
            return "\n🚨 **Требуется ваше внимание!**"
        return ""

    def _generate_ai_recommendation(self, change_data: Dict[str, Any], importance: float) -> str:
        """Generate AI recommendation based on change type and category."""
        try:
            possible_recommendations = []

            # Add recommendations based on notification type
            if change_data['type'] in self._recommendations:
                possible_recommendations.extend(self._recommendations[change_data['type']])

            # Add recommendations based on category
            category = change_data.get('category')
            if category and category in self._recommendations:
                possible_recommendations.extend(self._recommendations[category])

            return random.choice(possible_recommendations) if possible_recommendations else ""
        except Exception as e:
            logger.warning(f"Error generating AI recommendation: {e}")
            return ""


class WebsiteChangeDetector:
    """Detects and categorizes changes on monitored websites."""

    @staticmethod
    def categorize_change(old_status: int, new_status: int, response_time: int) -> ChangeCategory:
        """
        Categorize website change based on status codes and response time.
        """
        if not all(isinstance(x, int) for x in [old_status, new_status, response_time]):
            raise ValidationError("Status codes and response time must be integers")

        try:
            if new_status != 200 and old_status == 200:
                return ChangeCategory.AVAILABILITY
            elif new_status == 200 and old_status != 200:
                return ChangeCategory.PERFORMANCE
            elif response_time > 1000:
                return ChangeCategory.PERFORMANCE
            elif "error" in str(new_status).lower() or new_status >= 500:
                return ChangeCategory.SECURITY
            elif new_status == 404:
                return ChangeCategory.STRUCTURE
            elif new_status in (301, 302):
                return ChangeCategory.SEO
            else:
                return ChangeCategory.CONTENT
        except Exception as e:
            logger.error(f"Error categorizing change: {e}")
            return ChangeCategory.CONTENT

    @staticmethod
    def detect_change_type(old_status: int, new_status: int, response_time: int) -> NotificationType:
        """
        Detect notification type based on change severity.
        """
        try:
            if new_status in (500, 503):
                return NotificationType.CRITICAL
            elif new_status != 200 and old_status == 200:
                return NotificationType.ERROR
            elif new_status == 200 and old_status != 200:
                return NotificationType.SUCCESS
            elif response_time > 3000:
                return NotificationType.CRITICAL
            elif response_time > 1000:
                return NotificationType.WARNING
            elif old_status and abs(new_status - old_status) >= 100:
                return NotificationType.WARNING
            else:
                return NotificationType.INFO
        except Exception as e:
            logger.error(f"Error detecting change type: {e}")
            return NotificationType.INFO


class WebsiteChecker:
    """Simulates website checking with realistic scenarios."""

    def __init__(self):
        self.scenarios = self._initialize_scenarios()
        logger.info("Website Checker initialized with realistic scenarios")

    def _initialize_scenarios(self) -> List[Dict[str, Any]]:
        """Initialize realistic website check scenarios with probabilities."""
        return [
            {'status': 200, 'content': 'stable', 'response_time': 150, 'probability': 0.6},
            {'status': 200, 'content': 'updated', 'response_time': 200, 'probability': 0.2},
            {'status': 404, 'content': 'error', 'response_time': 500, 'probability': 0.05},
            {'status': 503, 'content': 'unavailable', 'response_time': 1000, 'probability': 0.05},
            {'status': 500, 'content': 'server_error', 'response_time': 3000, 'probability': 0.03},
            {'status': 200, 'content': 'optimized', 'response_time': 100, 'probability': 0.05},
            {'status': 301, 'content': 'redirect', 'response_time': 300, 'probability': 0.02},
        ]

    def simulate_check(self, url: str, stability_score: float = 1.0) -> Dict[str, Any]:
        """
        Simulate website check with stability-aware scenario selection.
        """
        if not URLValidator.validate_url(url):
            raise ValidationError(f"Invalid URL: {url}")

        if not 0.0 <= stability_score <= 1.0:
            raise ValidationError(f"Stability score must be between 0.0 and 1.0, got {stability_score}")

        try:
            # More stable sites are less likely to show errors
            if stability_score > 0.8 and random.random() < 0.7:
                scenario = self.scenarios[0]  # Stable status
            else:
                scenario = self._select_scenario_by_probability()

            content_hash = hashlib.md5(
                f"{url}_{scenario['content']}_{datetime.now().timestamp()}_{secrets.token_hex(8)}".encode()
            ).hexdigest()

            result = {
                'status': scenario['status'],
                'content_hash': content_hash,
                'response_time': scenario['response_time'],
                'timestamp': datetime.now(),
                'scenario': scenario['content']
            }

            logger.debug(
                f"Simulated check for {url}: status {scenario['status']}, response {scenario['response_time']}ms")
            return result

        except Exception as e:
            logger.error(f"Error simulating check for {url}: {e}")
            raise MonitoringError(f"Website check simulation failed: {e}")

    def _select_scenario_by_probability(self) -> Dict[str, Any]:
        """Select scenario based on defined probabilities."""
        rand = random.random()
        cumulative_probability = 0.0

        for scenario in self.scenarios:
            cumulative_probability += scenario['probability']
            if rand <= cumulative_probability:
                return scenario

        # Fallback to first scenario
        return self.scenarios[0]


class AsyncSmartWebsiteMonitor:
    """
    AI-powered website monitoring system with smart notification filtering
    and personalized user experiences - ASYNC VERSION.
    """

    def __init__(self):
        self.monitored_urls: Dict[str, Dict[str, Any]] = {}
        self.user_subscriptions: Dict[int, Set[str]] = {}
        self.change_history: Dict[str, Dict[str, Any]] = {}
        self.ai_filter = AINotificationFilter()
        self.change_detector = WebsiteChangeDetector()
        self.website_checker = WebsiteChecker()
        self.url_validator = URLValidator()

        # Async monitoring task
        self._monitoring_task: Optional[asyncio.Task] = None
        self._stop_monitoring = False

        # Bot integration
        self._application: Optional[Application] = None

        # Statistics
        self._stats = {
            'websites_checked': 0,
            'changes_detected': 0,
            'notifications_sent': 0,
            'errors_encountered': 0,
            'start_time': datetime.now()
        }

        logger.info("Async Smart Website Monitor initialized successfully")

    def set_bot_instance(self, application_instance: Application) -> None:
        """
        Set Telegram bot application instance for message sending.
        """
        if application_instance is None:
            raise ConfigurationError("Application instance cannot be None")

        self._application = application_instance
        logger.info("Bot application instance configured")

    def subscribe_user(self, user_id: int, notification_types: Optional[List[NotificationType]] = None) -> bool:
        """
        Subscribe user to monitoring service with comprehensive validation.
        """
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValidationError(f"Invalid user ID: {user_id}")

        try:
            if user_id not in self.user_subscriptions:
                self.user_subscriptions[user_id] = set()

            self.ai_filter.analyze_user_behavior(user_id, 'subscribe', {
                'notification_types': [nt.value for nt in notification_types] if notification_types else []
            })

            logger.info(f"User {user_id} subscribed successfully")
            return True

        except Exception as e:
            logger.error(f"Error subscribing user {user_id}: {e}")
            raise MonitoringError(f"Failed to subscribe user: {e}")

    def unsubscribe_user(self, user_id: int) -> bool:
        """
        Unsubscribe user from monitoring service with cleanup.
        """
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValidationError(f"Invalid user ID: {user_id}")

        try:
            if user_id in self.user_subscriptions:
                user_urls = self.get_user_urls(user_id)
                for url in user_urls:
                    self.remove_url_monitoring(user_id, url)
                del self.user_subscriptions[user_id]
                self.ai_filter.analyze_user_behavior(user_id, 'unsubscribe')
                logger.info(f"User {user_id} unsubscribed successfully")
            return True

        except Exception as e:
            logger.error(f"Error unsubscribing user {user_id}: {e}")
            return False

    def add_url_monitoring(self, user_id: int, url: str) -> bool:
        """
        Add URL to monitoring for specific user with validation and limits.
        """
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValidationError(f"Invalid user ID: {user_id}")

        try:
            normalized_url = self.url_validator.normalize_url(url)
            self.url_validator.validate_url(normalized_url)
        except ValidationError as e:
            logger.error(f"URL validation failed for user {user_id}: {e}")
            raise

        # Check URL limits
        user_urls = self.get_user_urls(user_id)
        if len(user_urls) >= Config.MAX_URLS_PER_USER:
            raise ValidationError(f"User {user_id} has reached the maximum URL limit ({Config.MAX_URLS_PER_USER})")

        try:
            if normalized_url not in self.monitored_urls:
                self.monitored_urls[normalized_url] = self._create_url_monitoring_entry()

            self.monitored_urls[normalized_url]['users'].add(user_id)
            self.ai_filter.analyze_user_behavior(user_id, 'add_url', {'url': normalized_url})

            logger.info(f"URL {normalized_url} added to monitoring for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Error adding URL monitoring for user {user_id}: {e}")
            raise MonitoringError(f"Failed to add URL monitoring: {e}")

    def _create_url_monitoring_entry(self) -> Dict[str, Any]:
        """Create default URL monitoring entry with comprehensive tracking."""
        return {
            'users': set(),
            'last_check': None,
            'last_status': None,
            'last_hash': None,
            'change_frequency': 0,
            'stability_score': 1.0,
            'total_checks': 0,
            'total_changes': 0,
            'created_at': datetime.now(),
            'last_change': None
        }

    def remove_url_monitoring(self, user_id: int, url: str) -> bool:
        """
        Remove URL monitoring for specific user.
        """
        try:
            normalized_url = self.url_validator.normalize_url(url)

            if normalized_url in self.monitored_urls and user_id in self.monitored_urls[normalized_url]['users']:
                self.monitored_urls[normalized_url]['users'].remove(user_id)
                if not self.monitored_urls[normalized_url]['users']:
                    del self.monitored_urls[normalized_url]
                logger.info(f"URL {normalized_url} removed from monitoring for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Error removing URL monitoring for user {user_id}: {e}")
            return False

    def get_user_urls(self, user_id: int) -> List[str]:
        """
        Get all URLs monitored by user.
        """
        try:
            return [
                url for url, data in self.monitored_urls.items()
                if user_id in data.get('users', [])
            ]
        except Exception as e:
            logger.error(f"Error getting URLs for user {user_id}: {e}")
            return []

    def get_user_status(self, user_id: int) -> Dict[str, Any]:
        """
        Get comprehensive user status with AI preferences and statistics.
        """
        try:
            user_urls = self.get_user_urls(user_id)
            user_changes = self._get_user_changes(user_id, user_urls)
            profile = self.ai_filter.get_user_preferences(user_id)

            return {
                'subscribed': user_id in self.user_subscriptions,
                'monitored_urls': len(user_urls),
                'total_changes': len(user_changes),
                'preferences': profile,
                'importance_threshold': profile.get('importance_threshold', Config.INITIAL_IMPORTANCE_THRESHOLD),
                'reaction_stats': profile.get('reaction_stats', {}),
                'urls': user_urls[:10],
                'last_activity': self._get_user_last_activity(user_id)
            }
        except Exception as e:
            logger.error(f"Error getting status for user {user_id}: {e}")
            return {
                'subscribed': False,
                'monitored_urls': 0,
                'total_changes': 0,
                'error': str(e)
            }

    def _get_user_changes(self, user_id: int, user_urls: List[str]) -> List[Dict[str, Any]]:
        """Get changes relevant to specific user."""
        try:
            return [
                change for change in self.change_history.values()
                if (change['url'] in user_urls and
                    user_id in self.monitored_urls.get(change['url'], {}).get('users', []))
            ]
        except Exception as e:
            logger.error(f"Error getting user changes for {user_id}: {e}")
            return []

    def _get_user_last_activity(self, user_id: int) -> Optional[datetime]:
        """Get last activity timestamp for user."""
        return datetime.now()

    def check_website(self, url: str) -> ChangeDetectionResult:
        """
        Perform comprehensive website check and change detection.
        """
        start_time = datetime.now()

        try:
            if url not in self.monitored_urls:
                raise MonitoringError(f"URL {url} is not being monitored")

            current_data = self.website_checker.simulate_check(
                url,
                self.monitored_urls[url].get('stability_score', 1.0)
            )
            previous_data = self.monitored_urls[url]

            changes = self._detect_changes(url, current_data, previous_data)
            self._update_website_data(url, current_data, changes)

            self._stats['websites_checked'] += 1
            if changes:
                self._stats['changes_detected'] += len(changes)

            return ChangeDetectionResult(
                changes=changes,
                check_timestamp=current_data['timestamp'],
                website_status=current_data['status'],
                response_time=current_data['response_time'],
                success=True
            )

        except Exception as e:
            self._stats['errors_encountered'] += 1
            logger.error(f"Error checking website {url}: {e}")

            return ChangeDetectionResult(
                changes=[],
                check_timestamp=datetime.now(),
                website_status=0,
                response_time=0,
                success=False,
                error_message=str(e)
            )

    def _detect_changes(self, url: str, current_data: Dict[str, Any], previous_data: Dict[str, Any]) -> List[
        Dict[str, Any]]:
        """Detect all types of changes between current and previous state."""
        changes = []
        change_id = self._generate_change_id(url, current_data['timestamp'])

        # Detect status changes
        status_change = self._detect_status_change(url, change_id, current_data, previous_data)
        if status_change:
            changes.append(status_change)

        # Detect content changes
        content_change = self._detect_content_change(url, change_id, current_data, previous_data)
        if content_change:
            changes.append(content_change)

        # Detect initialization (first check)
        if previous_data.get('last_hash') is None:
            changes.append(self._create_initialization_change(url, change_id, current_data))

        return changes

    def _generate_change_id(self, url: str, timestamp: datetime) -> str:
        """Generate unique change identifier with collision protection."""
        return hashlib.md5(f"{url}_{timestamp.timestamp()}_{secrets.token_hex(4)}".encode()).hexdigest()[:12]

    def _detect_status_change(self, url: str, change_id: str, current_data: Dict[str, Any],
                              previous_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Detect HTTP status changes."""
        previous_status = previous_data.get('last_status')
        current_status = current_data['status']

        if previous_status is not None and previous_status != current_status:
            change_type = self.change_detector.detect_change_type(
                previous_status, current_status, current_data['response_time']
            )
            category = self.change_detector.categorize_change(
                previous_status, current_status, current_data['response_time']
            )

            return {
                'id': change_id,
                'type': change_type,
                'category': category,
                'description': f"Статус изменился: {previous_status} → {current_status}",
                'url': url,
                'timestamp': current_data['timestamp'],
                'response_time': current_data['response_time'],
                'importance': 0.0
            }
        return None

    def _detect_content_change(self, url: str, change_id: str, current_data: Dict[str, Any],
                               previous_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Detect content hash changes."""
        previous_hash = previous_data.get('last_hash')
        current_hash = current_data['content_hash']

        if previous_hash is not None and previous_hash != current_hash:
            return {
                'id': change_id + "_content",
                'type': NotificationType.UPDATE,
                'category': ChangeCategory.CONTENT,
                'description': "Обновление контента на сайте",
                'url': url,
                'timestamp': current_data['timestamp'],
                'response_time': current_data['response_time'],
                'importance': 0.0
            }
        return None

    def _create_initialization_change(self, url: str, change_id: str, current_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create initialization change for first check."""
        return {
            'id': change_id + "_init",
            'type': NotificationType.INFO,
            'category': ChangeCategory.AVAILABILITY,
            'description': "Мониторинг сайта начат",
            'url': url,
            'timestamp': current_data['timestamp'],
            'response_time': current_data['response_time'],
            'importance': 0.3
        }

    def _update_website_data(self, url: str, current_data: Dict[str, Any], changes: List[Dict[str, Any]]) -> None:
        """Update website data and metrics after check."""
        try:
            self.monitored_urls[url].update({
                'last_check': current_data['timestamp'],
                'last_status': current_data['status'],
                'last_hash': current_data['content_hash'],
                'stability_score': self._calculate_stability_score(url, changes),
                'total_checks': self.monitored_urls[url].get('total_checks', 0) + 1
            })

            if changes:
                self.monitored_urls[url]['total_changes'] = self.monitored_urls[url].get('total_changes', 0) + len(
                    changes)
                self.monitored_urls[url]['last_change'] = current_data['timestamp']

            # Save changes to history
            for change in changes:
                self.change_history[change['id']] = change

        except Exception as e:
            logger.error(f"Error updating website data for {url}: {e}")

    def _calculate_stability_score(self, url: str, changes: List[Dict[str, Any]]) -> float:
        """
        Calculate website stability score based on recent changes.
        """
        try:
            site_data = self.monitored_urls[url]
            current_stability = site_data.get('stability_score', 1.0)

            # Apply penalties for errors and warnings
            error_penalty = sum(
                0.2 if change['type'] in [NotificationType.ERROR, NotificationType.CRITICAL]
                else 0.1 if change['type'] == NotificationType.WARNING
                else 0
                for change in changes
            )

            new_stability = max(0.1, current_stability - error_penalty)

            # Gradual stability recovery
            recovery_rate = 0.05
            return min(1.0, new_stability + recovery_rate)
        except Exception as e:
            logger.error(f"Error calculating stability score for {url}: {e}")
            return 0.5

    async def start_async_monitoring(self) -> None:
        """
        Start the AI-powered monitoring system as an async task.
        """
        if self._stop_monitoring:
            logger.warning("Monitoring system is already stopping or stopped")
            return

        self._stop_monitoring = False
        self._monitoring_task = asyncio.create_task(self._monitoring_loop_async())
        logger.info("🔍 AI-powered monitoring system started successfully")

    async def _monitoring_loop_async(self) -> None:
        """Async monitoring loop that checks websites periodically."""
        logger.info("Async monitoring loop started")

        while not self._stop_monitoring:
            try:
                urls_to_check = list(self.monitored_urls.keys())

                if not urls_to_check:
                    logger.debug("No URLs to monitor, sleeping...")
                    await asyncio.sleep(Config.MONITORING_INTERVAL_SECONDS)
                    continue

                for url in urls_to_check:
                    if self._stop_monitoring:
                        break
                    await self._process_website_changes_async(url)

                await asyncio.sleep(Config.MONITORING_INTERVAL_SECONDS)

            except asyncio.CancelledError:
                logger.info("Monitoring loop cancelled")
                break
            except Exception as e:
                logger.error(f"Monitoring loop error: {e}")
                await asyncio.sleep(min(60, Config.MONITORING_INTERVAL_SECONDS * 2))

        logger.info("Async monitoring loop stopped")

    async def _process_website_changes_async(self, url: str) -> None:
        """Process changes for a specific website and notify users asynchronously."""
        try:
            result = self.check_website(url)

            if not result.success:
                logger.warning(f"Website check failed for {url}: {result.error_message}")
                return

            if result.changes:
                users = self.monitored_urls[url]['users']
                await self._notify_users_about_changes_async(users, result.changes)

        except Exception as e:
            logger.error(f"Error processing website changes for {url}: {e}")

    async def _notify_users_about_changes_async(self, users: Set[int], changes: List[Dict[str, Any]]) -> None:
        """Notify users about detected changes asynchronously."""
        for user_id in users:
            if self._stop_monitoring:
                break

            if user_id in self.user_subscriptions:
                await self._process_user_notifications_async(user_id, changes)

    async def _process_user_notifications_async(self, user_id: int, changes: List[Dict[str, Any]]) -> None:
        """Process and filter notifications for specific user asynchronously."""
        try:
            filtered_changes = [
                change for change in changes
                if self._should_notify_user(user_id, change)
            ]

            if filtered_changes:
                await self._send_user_notifications_async(user_id, filtered_changes)

        except Exception as e:
            logger.error(f"Error processing notifications for user {user_id}: {e}")

    def _should_notify_user(self, user_id: int, change: Dict[str, Any]) -> bool:
        """Determine if user should be notified about change."""
        try:
            change['importance'] = self.ai_filter.calculate_change_importance(user_id, change)
            return self.ai_filter.should_send_notification(user_id, change)
        except Exception as e:
            logger.error(f"Error determining notification for user {user_id}: {e}")
            return True

    async def _send_user_notifications_async(self, user_id: int, changes: List[Dict[str, Any]]) -> None:
        """Send filtered and grouped notifications to user asynchronously."""
        try:
            grouped_notifications = self.ai_filter.group_related_notifications(user_id, changes)

            for notification_group in grouped_notifications:
                if self._stop_monitoring:
                    break

                if len(notification_group) == 1:
                    await self._send_single_notification_async(user_id, notification_group[0])
                else:
                    await self._send_grouped_notification_async(user_id, notification_group)

        except Exception as e:
            logger.error(f"Error sending notifications to user {user_id}: {e}")

    async def _send_single_notification_async(self, user_id: int, change: Dict[str, Any]) -> None:
        """Send single notification asynchronously."""
        try:
            if not self._application:
                logger.error("Application instance not set, cannot send notification")
                return

            message = self.ai_filter.generate_personalized_message(user_id, change)
            reply_markup = self._create_feedback_keyboard(change['id'])

            success = await self._safe_send_message(user_id, message, reply_markup)
            if success:
                self._stats['notifications_sent'] += 1
                logger.info(f"Notification delivered to user {user_id}")

        except Exception as e:
            logger.error(f"Error sending single notification for user {user_id}: {e}")

    async def _send_grouped_notification_async(self, user_id: int, notifications: List[Dict[str, Any]]) -> None:
        """Send grouped notification asynchronously."""
        try:
            if not self._application or not notifications:
                return

            message = self._create_grouped_message(notifications)

            success = await self._safe_send_message(user_id, message)
            if success:
                self._stats['notifications_sent'] += 1
                logger.info(f"Grouped notification delivered to user {user_id} ({len(notifications)} changes)")

        except Exception as e:
            logger.error(f"Error sending grouped notification for user {user_id}: {e}")

    def _create_feedback_keyboard(self, change_id: str) -> InlineKeyboardMarkup:
        """Create feedback keyboard for notifications."""
        keyboard = [[
            InlineKeyboardButton("👍", callback_data=f"like_{change_id}"),
            InlineKeyboardButton("👎", callback_data=f"dislike_{change_id}"),
            InlineKeyboardButton("➖", callback_data=f"ignore_{change_id}")
        ]]
        return InlineKeyboardMarkup(keyboard)

    def _create_grouped_message(self, notifications: List[Dict[str, Any]]) -> str:
        """Create message for grouped notifications."""
        try:
            main_notification = notifications[0]
            message_lines = [
                f"📊 **AI-группа уведомлений ({len(notifications)})**",
                f"🌐 Сайт: {main_notification['url']}",
                f"📂 Категория: {main_notification.get('category', ChangeCategory.CONTENT).value}",
                ""
            ]

            # Add individual notifications
            for i, notification in enumerate(notifications[:5], 1):
                message_lines.append(f"{i}. {notification['type'].value}: {notification['description']}")

            if len(notifications) > 5:
                message_lines.append(f"\n... и еще {len(notifications) - 5} изменений")

            message_lines.append("\n💡 **AI сгруппировал связанные изменения для вашего удобства**")

            message = "\n".join(message_lines)

            # Ensure message length is within limits
            if len(message) > Config.MAX_MESSAGE_LENGTH:
                message = message[:Config.MAX_MESSAGE_LENGTH - 100] + "\n\n... (сообщение сокращено)"

            return message

        except Exception as e:
            logger.error(f"Error creating grouped message: {e}")
            return "Обнаружены изменения на сайте"

    async def _safe_send_message(self, user_id: int, message: str,
                                 reply_markup: Optional[InlineKeyboardMarkup] = None) -> bool:
        """
        Safely send message with retry logic and exponential backoff.
        """
        if not self._application:
            logger.error("Application not initialized")
            return False

        for attempt in range(Config.MAX_RETRY_ATTEMPTS):
            try:
                send_args = {
                    'chat_id': user_id,
                    'text': message,
                    'parse_mode': 'Markdown',
                    'timeout': Config.REQUEST_TIMEOUT
                }

                if reply_markup:
                    send_args['reply_markup'] = reply_markup

                await self._application.bot.send_message(**send_args)
                return True

            except RetryAfter as e:
                # Telegram rate limiting
                wait_time = e.retry_after
                logger.warning(f"Rate limited, waiting {wait_time}s before retry for user {user_id}")
                await asyncio.sleep(wait_time)
                continue

            except NetworkError as e:
                logger.warning(f"Network error on attempt {attempt + 1} for user {user_id}: {e}")
                if attempt < Config.MAX_RETRY_ATTEMPTS - 1:
                    await asyncio.sleep(2 ** attempt)
                continue

            except TelegramError as e:
                logger.error(f"Telegram error on attempt {attempt + 1} for user {user_id}: {e}")
                break

            except Exception as e:
                logger.error(f"Unexpected error on attempt {attempt + 1} for user {user_id}: {e}")
                if attempt < Config.MAX_RETRY_ATTEMPTS - 1:
                    await asyncio.sleep(2 ** attempt)
                continue

        logger.error(f"Failed to send message to user {user_id} after {Config.MAX_RETRY_ATTEMPTS} attempts")
        return False

    async def stop_monitoring_async(self) -> None:
        """Stop the monitoring system gracefully."""
        if self._stop_monitoring:
            return

        logger.info("Stopping async monitoring system...")
        self._stop_monitoring = True

        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                logger.info("Monitoring task cancelled successfully")

        logger.info("🔍 AI-powered monitoring system stopped gracefully")

    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive system statistics."""
        uptime = datetime.now() - self._stats['start_time']

        return {
            **self._stats,
            'uptime_seconds': uptime.total_seconds(),
            'monitored_urls_count': len(self.monitored_urls),
            'subscribed_users_count': len(self.user_subscriptions)
        }

    def handle_user_feedback(self, notification_id: str, user_id: int,
                             reaction: UserReaction) -> None:
        """
        Handle user feedback for AI learning with validation.
        """
        if not notification_id:
            raise ValidationError("Notification ID cannot be empty")

        if not isinstance(user_id, int) or user_id <= 0:
            raise ValidationError(f"Invalid user ID: {user_id}")

        if not isinstance(reaction, UserReaction):
            raise ValidationError("Reaction must be a valid UserReaction enum value")

        try:
            self.ai_filter.record_notification_feedback(notification_id, user_id, reaction)
            logger.info(f"AI learning: user {user_id} reacted to notification {notification_id}: {reaction}")

        except Exception as e:
            logger.error(f"Error handling user feedback: {e}")
            raise MonitoringError(f"Failed to handle user feedback: {e}")


# Global monitor instance
monitor_system = AsyncSmartWebsiteMonitor()


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command with welcome message and basic instructions."""
    try:
        user = update.effective_user
        text = (
            f"👋 Привет, {user.first_name}!\n\n"
            "🤖 **AI-система умных уведомлений**\n\n"
            "🎯 **Новые AI-возможности:**\n"
            "• 🤖 Умная фильтрация по важности\n"
            "• 📊 AI-группировка уведомлений\n"
            "• 💡 Персонализированные рекомендации\n"
            "• 📈 Обучение на ваших реакциях\n"
            "• 🎛️ Автоматическая настройка чувствительности\n\n"
            "📋 **Команды:**\n"
            "/subscribe - Подписка с AI-фильтрацией\n"
            "/unsubscribe - Отписка\n"
            "/monitor [url] - Мониторинг сайта\n"
            "/status - Статус и AI-настройки\n"
            "/myurls - Мои сайты\n"
            "/settings - Настройки AI-фильтрации\n"
            "/help - Подробная справка\n\n"
            "🚀 **Начните с:** /subscribe"
        )
        await update.message.reply_text(text)
        logger.info(f"User {user.id} started the bot")

    except Exception as e:
        logger.error(f"Error in start_command: {e}")
        await update.message.reply_text("❌ Произошла ошибка. Пожалуйста, попробуйте позже.")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command with detailed instructions."""
    try:
        text = (
            "📚 **AI-СИСТЕМА УМНЫХ УВЕДОМЛЕНИЙ**\n\n"
            "🤖 **Как работает AI-фильтрация:**\n"
            "• 🔍 **AI-анализ важности** - оценивает каждое изменение\n"
            "• 📊 **Умная группировка** - объединяет связанные уведомления\n"
            "• 💡 **AI-обучение** - учится на ваших реакциях (👍/👎)\n"
            "• 🎛️ **Авто-адаптация** - настраивает чувствительность\n"
            "• ⏰ **Учет времени** - учитывает вашу активность\n\n"
            "🔔 **Типы уведомлений:**\n"
            "• 🔴 Критическое - требует немедленного внимания\n"
            "• 🚨 Ошибка - проблемы с доступностью\n"
            "• ⚠️ Предупреждение - важные изменения\n"
            "• ✅ Успех - восстановление работы\n"
            "• 🔄 Обновление - изменения контента\n"
            "• ℹ️ Информация - обычные изменения\n\n"
            "⚡ **Команды:**\n"
            "/subscribe - Активировать AI-фильтрацию\n"
            "/monitor [url] - Добавить сайт\n"
            "/status - Ваши AI-настройки\n"
            "/settings - Настроить фильтрацию\n"
            "/myurls - Список сайтов\n"
            "/unsubscribe - Отключить уведомления\n\n"
            "💡 **Совет:** Реагируйте на уведомления (👍/👎), чтобы улучшить AI!"
        )
        await update.message.reply_text(text)

    except Exception as e:
        logger.error(f"Error in help_command: {e}")
        await update.message.reply_text("❌ Произошла ошибка. Пожалуйста, попробуйте позже.")


async def subscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /subscribe command to activate AI filtering."""
    try:
        user = update.effective_user
        monitor_system.subscribe_user(user.id)

        status = monitor_system.get_user_status(user.id)
        threshold = status['importance_threshold']

        text = (
            "✅ **AI-фильтрация активирована!**\n\n"
            "🤖 **Система настроена и готова к работе:**\n\n"
            f"🎯 **Текущая чувствительность:** {threshold:.1%}\n"
            f"• Уведомления важнее этого порога будут приходить\n"
            f"• AI автоматически адаптируется под ваши предпочтения\n\n"
            "📊 **AI будет анализировать:**\n"
            "• Важность каждого изменения для вас\n"
            "• Ваши предпочтения и поведение\n"
            "• Время суток и активность\n"
            "• Историю ваших реакций\n\n"
            "💡 **Чтобы улучшить AI-фильтрацию:**\n"
            "• Реагируйте на уведомления (👍/👎)\n"
            "• Система учится на ваших предпочтениях\n"
            "• Чувствительность автоматически настраивается\n\n"
            "🎯 **Добавьте сайты для мониторинга:**\n"
            "`/monitor https://example.com`"
        )
        await update.message.reply_text(text)
        logger.info(f"User {user.id} subscribed to monitoring")

    except Exception as e:
        logger.error(f"Error in subscribe_command: {e}")
        await update.message.reply_text("❌ Произошла ошибка при подписке. Пожалуйста, попробуйте позже.")


async def unsubscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /unsubscribe command to deactivate monitoring."""
    try:
        user = update.effective_user
        monitor_system.unsubscribe_user(user.id)

        text = (
            "🔕 **AI-фильтрация отключена**\n\n"
            "Вы больше не будете получать умные уведомления.\n\n"
            "Все ваши AI-настройки и история обучения сохранены.\n"
            "Если решите вернуться, просто используйте:\n"
            "`/subscribe`\n\n"
            "Спасибо за использование нашей AI-системы! 👋"
        )

        await update.message.reply_text(text)
        logger.info(f"User {user.id} unsubscribed from monitoring")

    except Exception as e:
        logger.error(f"Error in unsubscribe_command: {e}")
        await update.message.reply_text("❌ Произошла ошибка при отписке. Пожалуйста, попробуйте позже.")


async def monitor_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /monitor command to add website for monitoring."""
    try:
        user = update.effective_user

        if not context.args:
            await update.message.reply_text(
                "❌ **Не указан URL сайта**\n\n"
                "📝 **Правильное использование:**\n"
                "`/monitor https://example.com`\n"
                "`/monitor https://google.com`\n\n"
                "💡 **Примеры:**\n"
                "`/monitor https://github.com`\n"
                "`/monitor https://youtube.com`\n\n"
                "⚠️ **Обязательно указывайте протокол (http:// или https://)**"
            )
            return

        url = context.args[0].strip()

        # Check subscription
        if not monitor_system.get_user_status(user.id)['subscribed']:
            await update.message.reply_text(
                "❌ **Сначала активируйте AI-фильтрацию!**\n\n"
                "Используйте команду:\n"
                "`/subscribe`\n\n"
                "После активации AI вы сможете добавлять сайты для умного мониторинга."
            )
            return

        # Add URL to monitoring
        monitor_system.add_url_monitoring(user.id, url)

        # Perform initial check
        await update.message.reply_text(f"🔍 **AI проверяет сайт...**\n\n`{url}`")
        result = monitor_system.check_website(url)

        # Send initial notifications
        if result.success and result.changes:
            for change in result.changes:
                if monitor_system.ai_filter.should_send_notification(user.id, change):
                    message = monitor_system.ai_filter.generate_personalized_message(user.id, change)
                    await update.message.reply_text(message)

        user_urls = monitor_system.get_user_urls(user.id)

        text = (
            f"✅ **Сайт добавлен в AI-мониторинг!**\n\n"
            f"🌐 **URL:** `{url}`\n"
            f"👤 **Пользователь:** {user.first_name}\n"
            f"📊 **Всего сайтов:** {len(user_urls)}\n\n"
            "🤖 **AI анализирует сайт...**\n"
            "🔔 Вы будете получать умные уведомления об изменениях!\n\n"
            "💡 **Что дальше?**\n"
            "• Добавьте еще сайтов\n"
            "• Проверьте AI-статус: `/status`\n"
            "• Посмотрите ваши сайты: `/myurls`"
        )
        await update.message.reply_text(text)
        logger.info(f"User {user.id} added URL to monitoring: {url}")

    except ValidationError as e:
        await update.message.reply_text(f"❌ **Ошибка валидации:** {e}")
    except MonitoringError as e:
        await update.message.reply_text(f"❌ **Ошибка мониторинга:** {e}")
    except Exception as e:
        logger.error(f"Error in monitor_command: {e}")
        await update.message.reply_text("❌ Произошла непредвиденная ошибка. Пожалуйста, попробуйте позже.")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status command to show user status and AI settings."""
    try:
        user = update.effective_user
        status = monitor_system.get_user_status(user.id)

        if status['subscribed']:
            user_urls = monitor_system.get_user_urls(user.id)
            preferences = status['preferences']
            reaction_stats = status['reaction_stats']

            total_reactions = sum(reaction_stats.values())
            if total_reactions > 0:
                like_percentage = (reaction_stats['likes'] / total_reactions) * 100
            else:
                like_percentage = 0

            text = (
                "📊 **AI-СТАТУС МОНИТОРИНГА**\n\n"
                f"👤 **Пользователь:** {user.first_name}\n"
                f"✅ **Статус:** AI-фильтрация активна\n"
                f"🌐 **Сайтов в мониторинге:** {status['monitored_urls']}\n"
                f"📈 **Всего изменений:** {status['total_changes']}\n"
                f"🎯 **Порог важности:** {status['importance_threshold']:.1%}\n\n"
            )

            if total_reactions > 0:
                text += f"📊 **AI-статистика реакций:**\n"
                text += f"• 👍 Нравится: {like_percentage:.1f}%\n"
                text += f"• 👎 Не нравится: {reaction_stats['dislikes']}\n"
                text += f"• ➖ Проигнорировано: {reaction_stats['ignores']}\n\n"

            if preferences:
                preferred_cats = [cat.value for cat in preferences.get('preferred_categories', [])]
                text += f"🎯 **Важные категории:** {', '.join(preferred_cats)}\n\n"

            if user_urls:
                text += "🌐 **Ваши сайты:**\n"
                for i, url in enumerate(user_urls[:5], 1):
                    url_data = monitor_system.monitored_urls.get(url, {})
                    last_check = url_data.get('last_check')
                    last_status = url_data.get('last_status')
                    stability = url_data.get('stability_score', 1.0)

                    status_emoji = "🟢" if last_status == 200 else "🔴" if last_status else "⚪"
                    stability_emoji = "🟢" if stability > 0.8 else "🟡" if stability > 0.5 else "🔴"

                    text += f"{i}. {status_emoji} `{url}`\n"
                    if last_check:
                        text += f"   ⏰ Проверка: {last_check.strftime('%H:%M')}\n"
                    text += f"   📊 Стабильность: {stability_emoji} {stability:.1%}\n"

            text += "\n💡 **AI-команды:**\n"
            text += "• Добавить сайт: `/monitor [url]`\n"
            text += "• Мои сайты: `/myurls`\n"
            text += "• Настройки AI: `/settings`\n"
            text += "• Отписаться: `/unsubscribe`"

        else:
            text = (
                "📊 **AI-СТАТУС МОНИТОРИНГА**\n\n"
                f"👤 **Пользователь:** {user.first_name}\n"
                f"❌ **Статус:** AI-фильтрация не активна\n"
                f"🌐 **Сайтов в мониторинге:** 0\n"
                f"📈 **Всего изменений:** 0\n\n"
                "🚀 **Чтобы начать AI-мониторинг:**\n"
                "1. Активируйте AI-фильтрацию: `/subscribe`\n"
                "2. Добавьте сайты: `/monitor [url]`\n"
                "3. Получайте умные уведомления!\n\n"
                "🤖 **AI будет анализировать изменения**\n"
                "и присылать персонализированные уведомления."
            )

        await update.message.reply_text(text)

    except Exception as e:
        logger.error(f"Error in status_command: {e}")
        await update.message.reply_text("❌ Произошла ошибка при получении статуса. Пожалуйста, попробуйте позже.")


async def my_urls_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /myurls command to show user's monitored websites."""
    try:
        user = update.effective_user
        user_urls = monitor_system.get_user_urls(user.id)

        if not user_urls:
            await update.message.reply_text(
                "📭 **У вас нет сайтов в AI-мониторинге**\n\n"
                "Добавьте сайты для умного мониторинга:\n"
                "`/monitor https://example.com`\n"
                "`/monitor https://google.com`\n\n"
                "💡 После добавления AI будет отслеживать изменения\n"
                "и присылать умные уведомления!"
            )
            return

        text = f"🌐 **ВАШИ САЙТЫ В AI-МОНИТОРИНГЕ ({len(user_urls)})**\n\n"

        for i, url in enumerate(user_urls, 1):
            url_data = monitor_system.monitored_urls.get(url, {})
            last_check = url_data.get('last_check')
            last_status = url_data.get('last_status')
            stability = url_data.get('stability_score', 1.0)

            status_emoji = "🟢" if last_status == 200 else "🔴" if last_status else "⚪"
            stability_emoji = "🟢" if stability > 0.8 else "🟡" if stability > 0.5 else "🔴"

            text += f"{i}. {status_emoji} `{url}`\n"
            if last_check:
                text += f"   ⏰ Проверка: {last_check.strftime('%H:%M')}\n"
            if last_status:
                text += f"   📊 Статус: {last_status}\n"
            text += f"   🎯 Стабильность: {stability_emoji} {stability:.1%}\n\n"

        text += (
            "💡 **AI-управление:**\n"
            "• Добавить сайт: `/monitor [url]`\n"
            "• AI-статус: `/status`\n"
            "• Настройки AI: `/settings`\n"
            "• Отписаться: `/unsubscribe`"
        )

        await update.message.reply_text(text)

    except Exception as e:
        logger.error(f"Error in my_urls_command: {e}")
        await update.message.reply_text("❌ Произошла ошибка при получении списка сайтов. Пожалуйста, попробуйте позже.")


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /settings command to configure AI filtering preferences."""
    try:
        user = update.effective_user

        if not monitor_system.get_user_status(user.id)['subscribed']:
            await update.message.reply_text(
                "❌ **Сначала активируйте AI-фильтрацию!**\n\n"
                "Используйте команду:\n"
                "`/subscribe`\n\n"
                "После активации вы сможете настроить AI под свои предпочтения."
            )
            return

        status = monitor_system.get_user_status(user.id)
        preferences = status['preferences']

        text = (
            "⚙️ **НАСТРОЙКИ AI-ФИЛЬТРАЦИИ**\n\n"
            f"🎯 **Текущий порог важности:** {status['importance_threshold']:.1%}\n"
            f"📊 **Стиль уведомлений:** {preferences.get('notification_style', 'detailed')}\n"
            f"🔔 **Чувствительность:** {preferences.get('sensitivity', 'medium')}\n\n"
            "💡 **AI автоматически настраивается на основе:**\n"
            "• Ваших реакций на уведомления\n"
            "• Времени суток и активность\n"
            "• Предпочтений по категориям\n\n"
            "📈 **Статистика реакций:**\n"
            f"• 👍 Лайков: {status['reaction_stats']['likes']}\n"
            f"• 👎 Дизлайков: {status['reaction_stats']['dislikes']}\n"
            f"• ➖ Игноров: {status['reaction_stats']['ignores']}\n\n"
            "🔄 **AI постоянно учится и адаптируется под ваши предпочтения!**"
        )

        # Create keyboard for quick settings
        keyboard = [
            [InlineKeyboardButton("Повысить чувствительность", callback_data="increase_sensitivity")],
            [InlineKeyboardButton("Понизить чувствительность", callback_data="decrease_sensitivity")],
            [InlineKeyboardButton("Подробный стиль", callback_data="style_detailed")],
            [InlineKeyboardButton("Краткий стиль", callback_data="style_brief")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(text, reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Error in settings_command: {e}")
        await update.message.reply_text("❌ Произошла ошибка при настройках. Пожалуйста, попробуйте позже.")


async def handle_feedback_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle user feedback on notifications."""
    try:
        query = update.callback_query
        await query.answer()

        user_id = query.from_user.id
        data = query.data

        # Parse reaction and notification ID
        if data.startswith('like_'):
            notification_id = data[5:]
            reaction = UserReaction.LIKE
            reaction_text = "👍"
        elif data.startswith('dislike_'):
            notification_id = data[8:]
            reaction = UserReaction.DISLIKE
            reaction_text = "👎"
        elif data.startswith('ignore_'):
            notification_id = data[7:]
            reaction = UserReaction.IGNORE
            reaction_text = "➖"
        else:
            return

        # Process feedback
        monitor_system.handle_user_feedback(notification_id, user_id, reaction)

        # Update message with confirmation
        await query.edit_message_text(
            f"{query.message.text}\n\n✅ **Ваша реакция записана: {reaction_text}**\n"
            "🤖 AI учтет ваше предпочтение для будущих уведомлений!"
        )
        logger.info(f"User {user_id} provided feedback: {reaction.value}")

    except Exception as e:
        logger.error(f"Error in handle_feedback_callback: {e}")
        try:
            await query.answer("❌ Ошибка обработки反馈. Попробуйте позже.", show_alert=True)
        except Exception:
            pass


async def handle_settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle settings callback queries."""
    try:
        query = update.callback_query
        await query.answer()

        user_id = query.from_user.id
        data = query.data

        profile = monitor_system.ai_filter.get_user_preferences(user_id)

        if data == "increase_sensitivity":
            profile['importance_threshold'] = max(0.1, profile['importance_threshold'] - 0.1)
            message = "✅ Чувствительность повышена! Вы будете получать больше уведомлений."
        elif data == "decrease_sensitivity":
            profile['importance_threshold'] = min(0.9, profile['importance_threshold'] + 0.1)
            message = "✅ Чувствительность понижена! Вы будете получать только важные уведомления."
        elif data == "style_detailed":
            profile['notification_style'] = 'detailed'
            message = "✅ Установлен подробный стиль уведомлений."
        elif data == "style_brief":
            profile['notification_style'] = 'brief'
            message = "✅ Установлен краткий стиль уведомлений."
        else:
            message = "❌ Неизвестная команда настроек."

        await query.edit_message_text(
            f"{query.message.text}\n\n{message}\n\n"
            f"🎯 **Новый порог важности:** {profile['importance_threshold']:.1%}"
        )
        logger.info(f"User {user_id} updated settings: {data}")

    except Exception as e:
        logger.error(f"Error in handle_settings_callback: {e}")
        try:
            await query.answer("❌ Ошибка обновления настроек. Попробуйте позже.", show_alert=True)
        except Exception:
            pass


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Global error handler for the bot."""
    try:
        logger.error(f"Bot error: {context.error}", exc_info=context.error)

        # Notify user about error if possible
        if update and update.effective_message:
            try:
                await update.effective_message.reply_text(
                    "❌ Произошла непредвиденная ошибка. "
                    "Пожалуйста, попробуйте еще раз или обратитесь к администратору."
                )
            except Exception:
                pass
    except Exception as e:
        logger.critical(f"Error in error handler: {e}")


def main() -> None:
    """
    Main application entry point with proper event loop handling.
    """
    try:
        logger.info("=" * 60)
        logger.info("🚀 TELEGRAM БОТ С AI-ФИЛЬТРАЦИЕЙ УВЕДОМЛЕНИЙ")
        logger.info("Version: 3.2.0 | Security Fixed Version")
        logger.info("=" * 60)

        # Validate configuration
        try:
            Config.validate_config()
            logger.info("✅ Configuration validated successfully")
        except ConfigurationError as e:
            logger.critical(f"Configuration error: {e}")
            sys.exit(1)

        # Create Telegram application
        application = Application.builder().token(Config.BOT_TOKEN).build()
        monitor_system.set_bot_instance(application)

        # Register command handlers
        command_handlers = [
            ("start", start_command),
            ("help", help_command),
            ("subscribe", subscribe_command),
            ("unsubscribe", unsubscribe_command),
            ("monitor", monitor_command),
            ("status", status_command),
            ("myurls", my_urls_command),
            ("settings", settings_command),
        ]

        for command, handler in command_handlers:
            application.add_handler(CommandHandler(command, handler))

        # Register callback handlers
        application.add_handler(CallbackQueryHandler(
            handle_feedback_callback,
            pattern="^(like|dislike|ignore)_"
        ))
        application.add_handler(CallbackQueryHandler(
            handle_settings_callback,
            pattern="^(increase_sensitivity|decrease_sensitivity|style_)"
        ))

        # Register error handler
        application.add_error_handler(error_handler)

        logger.info("✅ AI bot configured and ready for production")
        logger.info("📱 Write /start to your bot in Telegram")
        logger.info("⏹️  Press Ctrl+C to stop gracefully")

        # Start monitoring system as a background task
        monitoring_task = None

        # Create and run event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Start monitoring
            monitoring_task = loop.create_task(monitor_system.start_async_monitoring())

            # Run bot with polling
            loop.run_until_complete(application.run_polling(
                drop_pending_updates=True,
                allowed_updates=['message', 'callback_query'],
                close_loop=False  # Don't close the loop!
            ))

        except KeyboardInterrupt:
            logger.info("\n🛑 Received interrupt signal, shutting down gracefully...")
        finally:
            # Stop monitoring task
            if monitoring_task:
                loop.run_until_complete(monitor_system.stop_monitoring_async())

            # Cleanup
            if not loop.is_closed():
                loop.close()

            logger.info("✅ Application shutdown complete")

    except Exception as e:
        logger.critical(f"❌ Critical application error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()