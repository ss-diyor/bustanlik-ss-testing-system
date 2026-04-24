"""
Smart Notifications System
Intelligent notification tizimi - shaxsiylashtirilgan eslatmalar va bashoratlar
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

import pandas as pd
import numpy as np
import psycopg2
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
import joblib

from database import get_connection, release_connection, talaba_natijalari
from i18n import get_user_text

class NotificationType(Enum):
    """Notification turlari"""
    NEW_RESULT = "new_result"
    REMINDER = "reminder"
    ACHIEVEMENT = "achievement"
    PREDICTION = "prediction"
    MOTIVATION = "motivation"
    DEADLINE = "deadline"

class Priority(Enum):
    """Notification prioritetlari"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    URGENT = 4

@dataclass
class Notification:
    """Notification modeli"""
    user_id: int
    type: NotificationType
    title: str
    message: str
    priority: Priority
    data: Dict[str, Any] = None
    scheduled_time: datetime = None
    language: str = 'uz'

class SmartNotificationSystem:
    """Smart Notification System"""
    
    def __init__(self):
        self.notification_queue = []
        self.user_profiles = {}
        self.ml_model = None
        self.scaler = StandardScaler()
        self.is_trained = False
        
    async def initialize(self):
        """Tizimni ishga tushirish"""
        logging.info("Smart Notification System initializing...")
        await self.load_user_profiles()
        await self.train_ml_model()
        logging.info("Smart Notification System initialized successfully!")
    
    async def load_user_profiles(self):
        """Foydalanuvchi profillarini yuklash"""
        conn = get_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Barcha foydalanuvchilar va ularning test natijalari
        cur.execute("""
            SELECT u.user_id, u.language, t.kod, t.ismlar, t.sinf, t.yonalish,
                   COUNT(tn.id) as test_count,
                   AVG(tn.umumiy_ball) as avg_score,
                   MAX(tn.umumiy_ball) as max_score,
                   MIN(tn.umumiy_ball) as min_score,
                   MAX(tn.test_sanasi) as last_test_date
            FROM users u
            LEFT JOIN talabalar t ON t.user_id = u.user_id
            LEFT JOIN test_natijalari tn ON tn.talaba_kod = t.kod
            WHERE u.user_id IS NOT NULL
            GROUP BY u.user_id, t.kod, t.ismlar, t.sinf, t.yonalish, u.language
        """)
        
        users = cur.fetchall()
        cur.close()
        release_connection(conn)
        
        for user in users:
            if user['kod']:  # Faqat bog'langan o'quvchilar
                self.user_profiles[user['user_id']] = {
                    'language': user['language'] or 'uz',
                    'student_code': user['kod'],
                    'name': user['ismlar'],
                    'class': user['sinf'],
                    'direction': user['yonalish'],
                    'test_count': user['test_count'] or 0,
                    'avg_score': float(user['avg_score']) if user['avg_score'] else 0,
                    'max_score': float(user['max_score']) if user['max_score'] else 0,
                    'min_score': float(user['min_score']) if user['min_score'] else 0,
                    'last_test_date': user['last_test_date'],
                    'performance_trend': self.calculate_performance_trend(user['kod']),
                    'risk_level': self.calculate_risk_level(user['kod']),
                    'achievement_level': self.calculate_achievement_level(user['kod'])
                }
    
    def calculate_performance_trend(self, student_code: str) -> str:
        """O'quvchining performance trendini hisoblash"""
        results = talaba_natijalari(student_code, limit=5)
        if len(results) < 2:
            return "stable"
        
        scores = [r['umumiy_ball'] for r in results]
        
        # Trendni hisoblash (oxirgi 3 ta test)
        if len(scores) >= 3:
            recent_avg = sum(scores[-3:]) / 3
            earlier_avg = sum(scores[-5:-2]) / 3 if len(scores) >= 5 else scores[0]
            
            if recent_avg > earlier_avg + 5:
                return "improving"
            elif recent_avg < earlier_avg - 5:
                return "declining"
        
        return "stable"
    
    def calculate_risk_level(self, student_code: str) -> str:
        """Xavf darajasini hisoblash (ML model yordamida)"""
        results = talaba_natijalari(student_code, limit=10)
        if len(results) < 3:
            return "unknown"
        
        scores = [r['umumiy_ball'] for r in results]
        
        # Simple risk calculation
        avg_score = sum(scores) / len(scores)
        last_score = scores[0]
        
        if avg_score < 50 and last_score < 45:
            return "high"
        elif avg_score < 60 or last_score < 55:
            return "medium"
        else:
            return "low"
    
    def calculate_achievement_level(self, student_code: str) -> str:
        """Yutuq darajasini hisoblash"""
        results = talaba_natijalari(student_code)
        if not results:
            return "beginner"
        
        scores = [r['umumiy_ball'] for r in results]
        max_score = max(scores)
        avg_score = sum(scores) / len(scores)
        
        if max_score >= 90 and avg_score >= 80:
            return "excellent"
        elif max_score >= 80 and avg_score >= 70:
            return "good"
        elif max_score >= 70 and avg_score >= 60:
            return "average"
        else:
            return "needs_improvement"
    
    async def train_ml_model(self):
        """ML modelini o'qitish"""
        try:
            # Ma'lumotlarni tayyorlash
            features = []
            labels = []
            
            for user_id, profile in self.user_profiles.items():
                if profile['test_count'] >= 3:
                    feature_vector = [
                        profile['test_count'],
                        profile['avg_score'],
                        profile['max_score'],
                        profile['min_score'],
                        1 if profile['performance_trend'] == 'improving' else 0,
                        1 if profile['performance_trend'] == 'declining' else 0,
                        1 if profile['risk_level'] == 'high' else 0,
                        1 if profile['risk_level'] == 'medium' else 0,
                    ]
                    
                    features.append(feature_vector)
                    # Label: next test will be better than average?
                    labels.append(1 if profile['performance_trend'] == 'improving' else 0)
            
            if len(features) >= 10:  # Kamida 10 ta namuna bo'lishi kerak
                X = np.array(features)
                y = np.array(labels)
                
                # Modelni o'qitish
                self.ml_model = RandomForestClassifier(n_estimators=10, random_state=42)
                self.scaler.fit(X)
                X_scaled = self.scaler.transform(X)
                self.ml_model.fit(X_scaled, y)
                self.is_trained = True
                
                logging.info(f"ML model trained with {len(features)} samples")
            else:
                logging.warning("Not enough data to train ML model")
        
        except Exception as e:
            logging.error(f"Error training ML model: {e}")
    
    async def predict_student_performance(self, student_code: str) -> Dict[str, Any]:
        """O'quvchining kelajakdagi performanceini bashorat qilish"""
        if not self.is_trained or student_code not in [p['student_code'] for p in self.user_profiles.values()]:
            return {"prediction": "unknown", "confidence": 0.0}
        
        # Feature vector tayyorlash
        user_profile = next(p for p in self.user_profiles.values() if p['student_code'] == student_code)
        
        features = np.array([[
            user_profile['test_count'],
            user_profile['avg_score'],
            user_profile['max_score'],
            user_profile['min_score'],
            1 if user_profile['performance_trend'] == 'improving' else 0,
            1 if user_profile['performance_trend'] == 'declining' else 0,
            1 if user_profile['risk_level'] == 'high' else 0,
            1 if user_profile['risk_level'] == 'medium' else 0,
        ]])
        
        # Bashorat qilish
        features_scaled = self.scaler.transform(features)
        prediction = self.ml_model.predict(features_scaled)[0]
        probability = self.ml_model.predict_proba(features_scaled)[0]
        
        return {
            "prediction": "improving" if prediction == 1 else "stable",
            "confidence": max(probability),
            "risk_level": user_profile['risk_level'],
            "recommendation": self.generate_recommendation(user_profile)
        }
    
    def generate_recommendation(self, profile: Dict[str, Any]) -> str:
        """Shaxsiy tavsiya generatsiya qilish"""
        language = profile['language']
        
        if profile['risk_level'] == 'high':
            if language == 'ru':
                return "Рекомендуется уделить больше времени подготовке и обратиться за помощью к учителям."
            elif language == 'en':
                return "It's recommended to spend more time on preparation and seek help from teachers."
            else:
                return "Ko'proq vaqt ajratish va o'qituvchilardan yordam so'rash tavsiya etiladi."
        
        elif profile['performance_trend'] == 'declining':
            if language == 'ru':
                return "Ваши результаты снижаются. Рассмотрите возможность изменения стратегии подготовки."
            elif language == 'en':
                return "Your performance is declining. Consider changing your preparation strategy."
            else:
                return "Natijangiz pasayib bormoqda. Tayyorlash strategiyasini o'zgartirishni ko'ring."
        
        else:
            if language == 'ru':
                return "Отличная работа! Продолжайте в том же духе."
            elif language == 'en':
                return "Great work! Keep up the good performance."
            else:
                return "Ajoyib ish! Shu tarzda davom eting."
    
    async def create_notification(self, user_id: int, notification_type: NotificationType, 
                                 title: str, message: str, priority: Priority = Priority.MEDIUM,
                                 data: Dict[str, Any] = None) -> Notification:
        """Notification yaratish"""
        language = self.user_profiles.get(user_id, {}).get('language', 'uz')
        
        notification = Notification(
            user_id=user_id,
            type=notification_type,
            title=get_user_text(user_id, title),
            message=get_user_text(user_id, message, **data or {}),
            priority=priority,
            data=data,
            language=language
        )
        
        return notification
    
    async def send_achievement_notification(self, user_id: int, achievement: str):
        """Yutuq notification yuborish"""
        notification = await self.create_notification(
            user_id=user_id,
            notification_type=NotificationType.ACHIEVEMENT,
            title="notifications.achievement",
            message="notifications.achievement",
            priority=Priority.HIGH,
            data={"yutuq": achievement}
        )
        
        await self.queue_notification(notification)
    
    async def send_prediction_notification(self, user_id: int, prediction: Dict[str, Any]):
        """Bashorat notification yuborish"""
        notification = await self.create_notification(
            user_id=user_id,
            notification_type=NotificationType.PREDICTION,
            title="notifications.prediction",
            message="notifications.prediction",
            priority=Priority.MEDIUM,
            data=prediction
        )
        
        await self.queue_notification(notification)
    
    async def queue_notification(self, notification: Notification):
        """Notificationni navbatga qo'yish"""
        self.notification_queue.append(notification)
        # Prioritet bo'yicha saralash
        self.notification_queue.sort(key=lambda x: x.priority.value, reverse=True)
    
    async def process_notifications(self, bot):
        """Notificationlarni qayta ishlash"""
        while self.notification_queue:
            notification = self.notification_queue.pop(0)
            
            try:
                await bot.send_message(
                    notification.user_id,
                    f"🔔 **{notification.title}**\n\n{notification.message}",
                    parse_mode="Markdown"
                )
                
                # Log qilish
                logging.info(f"Notification sent to user {notification.user_id}: {notification.type.value}")
                
            except Exception as e:
                logging.error(f"Error sending notification to {notification.user_id}: {e}")
    
    async def run_daily_analysis(self, bot):
        """Kundalik analiz va notificationlar"""
        logging.info("Running daily analysis...")
        
        # Xavf ostidagi o'quvchilarni aniqlash
        at_risk_students = [
            user_id for user_id, profile in self.user_profiles.items()
            if profile['risk_level'] == 'high'
        ]
        
        # Yutuqlarni aniqlash
        achieving_students = [
            user_id for user_id, profile in self.user_profiles.items()
            if profile['achievement_level'] == 'excellent'
        ]
        
        # Notificationlarni yuborish
        for user_id in at_risk_students:
            await self.send_prediction_notification(user_id, {
                "prediction": "needs_attention",
                "recommendation": self.generate_recommendation(self.user_profiles[user_id])
            })
        
        for user_id in achieving_students:
            await self.send_achievement_notification(user_id, "🏆 Excellent performance!")
        
        # Notificationlarni qayta ishlash
        await self.process_notifications(bot)
        
        logging.info(f"Daily analysis completed. {len(at_risk_students)} at-risk students, {len(achieving_students)} achieving students identified.")

# Global instance
smart_notifications = SmartNotificationSystem()

# Background task
async def run_smart_notifications(bot):
    """Smart notifications background task"""
    await smart_notifications.initialize()
    
    while True:
        try:
            # Har 6 soatda bir analiz
            await smart_notifications.run_daily_analysis(bot)
            await asyncio.sleep(6 * 60 * 60)  # 6 hours
            
        except Exception as e:
            logging.error(f"Error in smart notifications: {e}")
            await asyncio.sleep(60 * 60)  # 1 hour on error
