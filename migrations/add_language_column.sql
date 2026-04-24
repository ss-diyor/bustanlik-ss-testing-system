-- Multi-language support uchun language ustunini qo'shish
-- Migration: 001_add_language_column.sql

-- Users jadvaliga language ustunini qo'shish
ALTER TABLE users 
ADD COLUMN IF NOT EXISTS language VARCHAR(2) DEFAULT 'uz';

-- Default qiymatni o'rnatish (agar mavjud bo'lmasa)
UPDATE users 
SET language = 'uz' 
WHERE language IS NULL;

-- Index qo'shish (performance uchun)
CREATE INDEX IF NOT EXISTS idx_users_language ON users(language);

-- Test qilish
SELECT COUNT(*) as total_users, 
       COUNT(CASE WHEN language = 'uz' THEN 1 END) as uzbek_users,
       COUNT(CASE WHEN language = 'ru' THEN 1 END) as russian_users,
       COUNT(CASE WHEN language = 'en' THEN 1 END) as english_users
FROM users;

COMMENT ON COLUMN users.language IS 'Foydalanuvchi tanlagan til: uz, ru, en';
