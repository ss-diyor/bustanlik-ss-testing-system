-- Migration: Sertifikat hash ustuni qo'shish
-- Blockchain-ga asoslangan tekshiruv uchun

ALTER TABLE talabalar
  ADD COLUMN IF NOT EXISTS cert_hash TEXT DEFAULT NULL;

COMMENT ON COLUMN talabalar.cert_hash IS
  'SHA-256 hash: sertifikat haqiqiyligini tekshirish uchun (qalbakilashtirishning oldini oladi)';
