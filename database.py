# database.py
import aiosqlite

DB_NAME = "zingo_bot.db"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        # جدول کاربران و اساتید
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                role TEXT DEFAULT 'student',
                full_name TEXT,
                phone TEXT,
                placement_score INTEGER DEFAULT 0,
                placement_level TEXT DEFAULT 'None',
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # جدول رزومه و اطلاعات اساتید
        await db.execute("""
            CREATE TABLE IF NOT EXISTS teachers (
                user_id INTEGER PRIMARY KEY,
                experience TEXT,
                specialties TEXT,
                resume_file_id TEXT,
                demo_voice_id TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # جدول تراکنش‌ها و فیش‌های واریزی
        await db.execute("""
            CREATE TABLE IF NOT EXISTS receipts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                course_name TEXT,
                receipt_file_id TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()

async def get_user(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT user_id, role, full_name, phone, placement_score, placement_level FROM users WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchone()

async def save_user(user_id: int, role: str, full_name: str, phone: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT INTO users (user_id, role, full_name, phone)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                role=excluded.role,
                full_name=excluded.full_name,
                phone=excluded.phone
        """, (user_id, role, full_name, phone))
        await db.commit()

async def save_placement_result(user_id: int, score: int, level: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            UPDATE users 
            SET placement_score = ?, placement_level = ?
            WHERE user_id = ?
        """, (score, level, user_id))
        await db.commit()

async def save_teacher_application(user_id: int, experience: str, specialties: str, resume_file_id: str, demo_voice_id: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT INTO teachers (user_id, experience, specialties, resume_file_id, demo_voice_id)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                experience=excluded.experience,
                specialties=excluded.specialties,
                resume_file_id=excluded.resume_file_id,
                demo_voice_id=excluded.demo_voice_id
        """, (user_id, experience, specialties, resume_file_id, demo_voice_id))
        await db.commit()

async def save_receipt(user_id: int, course_name: str, file_id: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT INTO receipts (user_id, course_name, receipt_file_id)
            VALUES (?, ?, ?)
        """, (user_id, course_name, file_id))
        await db.commit()
