from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession
from sqlalchemy.orm import DeclarativeBase

#数据库的相关配置(注:用的sqlite，方便本地运行)

DATABASE_URL = "sqlite+aiosqlite:///./chat.db"

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Migration: add file_name column to resources if not exists
        try:
            await conn.exec_driver_sql(
                "ALTER TABLE resources ADD COLUMN file_name VARCHAR DEFAULT ''"
            )
        except Exception:
            pass  # column already exists


async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session
