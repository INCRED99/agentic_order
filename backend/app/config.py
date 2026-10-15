from pydantic_settings import BaseSettings, SettingsConfigDict  # BaseSettings fills fields from env vars and the .env file


class Settings(BaseSettings):  # one class that holds every setting the app needs
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")  # also read .env, skip unknown lines

    supabase_url: str  # required: your Supabase project URL
    supabase_service_role_key: str  # required: backend-only key, bypasses RLS
    shared_inbox: str = "mealdesk.orders@gmail.com"  # the one Gmail inbox all restaurants share
    frontend_origins: str = "http://localhost:5173,https://agentic-order.vercel.app"  # comma separated list of allowed browser origins
    brevo_api_key: str = ""
    inbox_app_password: str = ""  # Gmail app password; empty default so the API starts without it, the worker checks it
    imap_host: str = "imap.gmail.com"  # server used to read mail
    smtp_host: str = "smtp.gmail.com"  # server used to send mail
    smtp_port: int = 465  # 465 = SMTP over SSL from the first byte
    poll_interval_seconds: int = 30  # pause between inbox checks
    lookback_days: int = 2  # days of mail listed on every poll (your decision: DB unique key + 2-day window)
    unknown_reply_daily_cap: int = 50  # max "unknown address" replies per 24 hours, protects Gmail's send limit
    max_body_chars: int = 5000  # longest mail body we store, limits size and room for prompt injection

    groq_api_key: str = ""  # Groq key for the agent, empty default so the API and worker start without it
    llm_model: str = "openai/gpt-oss-120b"  # primary model id for the agent
    llm_fallback_model: str = "qwen/qwen3.8-27b"  # used when the primary fails or is rate limited
    razorpay_key_id: str = ""  # Razorpay TEST key id, starts with rzp_test_, empty default so the API starts without it
    razorpay_key_secret: str = ""  # Razorpay TEST key secret, backend only, never sent to the browser
    razorpay_webhook_secret: str = ""  # secret you type into the Razorpay webhook settings, used to verify webhook signatures

    @property  # lets other files write settings.origins without brackets
    def origins(self) -> list[str]:  # turns the comma string into a list
        return [o.strip() for o in self.frontend_origins.split(",") if o.strip()]  # split, trim spaces, drop empty pieces

    # DECISION PROBLEM: how do we make sure live Razorpay keys can never be used by mistake?
    # Options: (1) trust whoever fills .env, (2) refuse to run payment code unless the key id starts with rzp_test_.
    # Chosen: option 2. Reason: this project only ever takes test payments, and a live key pasted by accident would charge real money.
    # Cost: moving to live mode later means changing this one check on purpose.
    @property  # lets other files write settings.razorpay_is_test
    def razorpay_is_test(self) -> bool:  # True only when a test key id is set
        return self.razorpay_key_id.startswith("rzp_test_")  # Razorpay test key ids always start with rzp_test_


settings = Settings()  # one shared instance, other files import this