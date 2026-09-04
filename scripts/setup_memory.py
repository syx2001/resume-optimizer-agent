#初始化数据库表
from app.infrastructure.database.postgres import checkpointer, store

checkpointer.setup()
store.setup()

print("PostgreSQL checkpointer initialized.")
