from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    data_dir: str = os.environ.get("DATA_DIR", "./data")
    database_url: str = ""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        os.makedirs(self.data_dir, exist_ok=True)
        object.__setattr__(self, 'database_url', f"sqlite:///{self.data_dir}/oannes.db")

settings = Settings()
