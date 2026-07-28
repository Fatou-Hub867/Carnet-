from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    debug: bool = False

    database_url: str

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    password_reset_token_expire_minutes: int = 30

    s3_endpoint_url: str
    s3_access_key: str
    s3_secret_key: str
    s3_bucket_name: str
    s3_region: str = "us-east-1"

    resend_api_key: str
    email_from_address: str

    frontend_base_url: str


settings = Settings()
