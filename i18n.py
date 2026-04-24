"""
Internationalization (i18n) tizimi
O'zbek, Ingliz va Rus tillarini qo'llab-quvvatlash
"""

import json
import os
from typing import Dict, Any
from database import get_user, update_user_language

class I18nManager:
    """Xalqaro til qo'llab-quvvatlash menejeri"""
    
    def __init__(self):
        self.default_language = 'uz'
        self.supported_languages = ['uz', 'ru', 'en']
        self.translations = {}
        self.load_translations()
    
    def load_translations(self):
        """Barcha tillarning tarjimalarini yuklash"""
        for lang in self.supported_languages:
            file_path = f'locales/{lang}.json'
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    self.translations[lang] = json.load(f)
            else:
                self.translations[lang] = {}
    
    def get_translation(self, key: str, language: str = None, **kwargs) -> str:
        """Tarjima qilingan matnni olish"""
        if language is None:
            language = self.default_language
        
        # Agar til mavjud bo'lmasa, default tilga qaytish
        if language not in self.supported_languages:
            language = self.default_language
        
        # Kalit bo'yicha tarjima qidirish
        translation = self._get_nested_value(self.translations.get(language, {}), key)
        
        # Agar tarjima topilmasa, default tilga qarab qidirish
        if translation is None and language != self.default_language:
            translation = self._get_nested_value(self.translations.get(self.default_language, {}), key)
        
        # Agar hali ham topilmasa, kalitni o'zi qaytarish
        if translation is None:
            translation = key
        
        # Formatlash (agar kerak bo'lsa)
        if kwargs:
            try:
                translation = translation.format(**kwargs)
            except (KeyError, ValueError):
                pass
        
        return translation
    
    def _get_nested_value(self, data: Dict, key: str) -> str:
        """Nested kalit bo'yicha qiymat olish"""
        keys = key.split('.')
        value = data
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return None
        
        return value
    
    def get_user_language(self, user_id: int) -> str:
        """Foydalanuvchi tilini olish"""
        user = get_user(user_id)
        if user and user.get('language'):
            return user['language']
        return self.default_language
    
    def set_user_language(self, user_id: int, language: str) -> bool:
        """Foydalanuvchi tilini o'rnatish"""
        if language in self.supported_languages:
            return update_user_language(user_id, language)
        return False
    
    def get_available_languages(self) -> Dict[str, str]:
        """Mavjud tillar ro'yxati"""
        return {
            'uz': '🇺🇿 O\'zbekcha',
            'ru': '🇷🇺 Русский', 
            'en': '🇬🇧 English'
        }

# Global i18n instance
i18n = I18nManager()

# Qulaylik funksiyalari
def _(key: str, language: str = None, **kwargs) -> str:
    """Tarjima qilish uchun qisqa funksiya"""
    return i18n.get_translation(key, language, **kwargs)

def get_user_text(user_id: int, key: str, **kwargs) -> str:
    """Foydalanuvchi tiliga qarab matn olish"""
    language = i18n.get_user_language(user_id)
    return i18n.get_translation(key, language, **kwargs)
