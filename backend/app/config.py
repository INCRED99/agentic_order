from pydantic_settings import BaseSettings, SettingsConfigDict  # BaseSettings fills fields from env vars and the .env file


class Settings(BaseSettings):  # one class that holds every setting the app needs
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")  # also read .env, skip unknown lines

    supabase_url: str  # required: your Supabase project URL
    supabase_service_role_key: str  # required: backend-only key, bypasses RLS
    shared_inbox: str = "mealdesk.orders@gmail.com"  # the one Gmail inbox all restaurants share
    frontend_origins: str = "http://localhost:5173"  # comma separated list of allowed browser origins

    inbox_app_password: str = ""  # Gmail app password; empty default so the API starts without it, the worker checks it
    imap_host: str = "imap.gmail.com"  # server used to read mail
    smtp_host: str = "smtp.gmail.com"  # server used to send mail
    smtp_port: int = 465  # 465 = SMTP over SSL from the first byte
    poll_interval_seconds: int = 30  # pause between inbox checks
    lookback_days: int = 2  # days of mail listed on every poll (your decision: DB unique key + 2-day window)
    unknown_reply_daily_cap: int = 50  # max "unknown address" replies per 24 hours, protects Gmail's send limit
    max_body_chars: int = 5000  # longest mail body we store, limits size and room for prompt injection

    @property  # lets other files write settings.origins without brackets
    def origins(self) -> list[str]:  # turns the comma string into a list
        return [o.strip() for o in self.frontend_origins.split(",") if o.strip()]  # split, trim spaces, drop empty pieces


settings = Settings()  # one shared instance, other files import this