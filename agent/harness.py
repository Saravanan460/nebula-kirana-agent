import os
from dataclasses import dataclass
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.groq import GroqModel
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.groq import GroqProvider
from groq import AsyncGroq


from agent.prompts import SYSTEM_PROMPT
from tools.inventory import add_product, receive_stock, check_stock, low_stock_report, search_product, list_all_products
from tools.billing import start_bill, add_item_to_bill, edit_bill_item, view_bill, finalize_bill, cancel_bill
from tools.khata import create_khata, charge_khata, pay_khata, check_khata
from tools.preferences import set_preference, get_preferences
from tools.documents import generate_invoice_pdf, generate_analysis_pptx
from tools.analytics import daily_summary, close_day

@dataclass
class AgentDeps:
    chat_id: int
    message_id: int

def _build_models():
    """Build available models AFTER dotenv has been loaded."""
    models = []
    if os.environ.get("GROQ_API_KEY"):
        # max_retries=0 disables Groq SDK's internal 429 retry loop
        # so our fallback handler can instantly switch to the next model
        async_groq = AsyncGroq(api_key=os.environ["GROQ_API_KEY"], max_retries=0)
        provider = GroqProvider(groq_client=async_groq)
        
        # Groq rate limits are PER MODEL. By adding multiple models,
        # we effectively multiply our free tier limits by switching buckets!
        models.append(("qwen", GroqModel('qwen/qwen3.8-27b', provider=provider)))
        models.append(("gpt-oss-20b", GroqModel('openai/gpt-oss-20b', provider=provider)))
        models.append(("gpt-oss-120b", GroqModel('openai/gpt-oss-120b', provider=provider)))
    if os.environ.get("GEMINI_API_KEY"):
        # Gemini limits are PER MODEL (20 requests/day/model).
        # By chaining models that actually exist in your account, we get more quota!
        models.append(("gemini-lite", GoogleModel('gemini-3.5-flash-lite')))
        models.append(("gemini-37", GoogleModel('gemini-3.7-flash')))
        models.append(("gemini-38", GoogleModel('gemini-3.8-flash')))
        models.append(("gemini-36", GoogleModel('gemini-3.6-flash')))
    from pydantic_ai.models.fallback import FallbackModel
    
    if not models:
        raise RuntimeError("No API key found. Set GROQ_API_KEY or GEMINI_API_KEY in .env")
        
    # Return a single FallbackModel that handles all API failures natively
    # without restarting the agent loop and causing duplicate tool executions
    return FallbackModel(*[m for name, m in models])

# Agent is created with a placeholder; model is swapped in init_agent()
agent = Agent(
    'test',  # placeholder — replaced before first use
    system_prompt="You are a helpful Kirana store agent.",
    deps_type=AgentDeps
)

# List of (name, model) tuples; first is primary, rest are fallbacks
_available_models: list = []

def init_agent():
    """Initialize agent and trigger fast fail if API keys are missing."""
    global _available_models
    _available_models = _build_models()
    agent._model = _available_models
    print("Agent initialized with models.")
    print(f"Agent initialized with FallbackModel.")

def get_fallback_models():
    """Return list of (name, model) tuples for fallback handling."""
    return _available_models

@agent.system_prompt
def add_dynamic_system_prompt(ctx: RunContext[AgentDeps]) -> str:
    """Injects chat-specific preferences into the system prompt."""
    chat_id = ctx.deps.chat_id
    prefs = get_preferences(chat_id)
    prefs_str = "\n".join([f"- {k}: {v}" for k, v in prefs.items()]) if prefs else "No preferences set yet."
    return SYSTEM_PROMPT.format(preferences_str=prefs_str)

# Register Inventory Tools
@agent.tool
def tool_add_product(ctx: RunContext[AgentDeps], name: str, sku: str, hsn_code: str, unit: str, is_loose: bool, cost_price: float, mrp: float, gst_rate: float, reorder_level: float = 10.0) -> str:
    """Add a new product (SKU) to the inventory."""
    return add_product(ctx.deps.chat_id, name, sku, hsn_code, unit, is_loose, cost_price, mrp, gst_rate, reorder_level)

@agent.tool
def tool_receive_stock(ctx: RunContext[AgentDeps], sku: str, quantity: float, new_cost_price: float = None, new_mrp: float = None) -> str:
    """Receive new stock for an existing product. 
    IMPORTANT: You must provide the EXACT SKU. If the user provides a product name, use tool_search_product first to find the exact SKU."""
    return receive_stock(ctx.deps.chat_id, sku, quantity, new_cost_price, new_mrp)

@agent.tool
def tool_check_stock(ctx: RunContext[AgentDeps], sku: str) -> str:
    """Check stock for a specific SKU. 
    IMPORTANT: You must provide the EXACT SKU. If the user provides a product name, use tool_search_product first to find the exact SKU. DO NOT guess the SKU."""
    return check_stock(ctx.deps.chat_id, sku)

@agent.tool
def tool_low_stock_report(ctx: RunContext[AgentDeps]) -> str:
    """Get a list of all products that are at or below their reorder level."""
    return low_stock_report(ctx.deps.chat_id)

@agent.tool
def tool_search_product(ctx: RunContext[AgentDeps], query: str) -> str:
    """Fuzzy search for products by name to find their SKUs and details."""
    return search_product(ctx.deps.chat_id, query)

@agent.tool
def tool_list_all_products(ctx: RunContext[AgentDeps]) -> str:
    """List all products available in the inventory."""
    return list_all_products(ctx.deps.chat_id)

# Register Billing Tools
@agent.tool
def tool_start_bill(ctx: RunContext[AgentDeps]) -> str:
    """Start a new draft bill for the current chat."""
    return start_bill(ctx.deps.chat_id)

@agent.tool
def tool_add_item_to_bill(ctx: RunContext[AgentDeps], sku: str, quantity: float) -> str:
    """Add a product to the current draft bill.
    IMPORTANT: You must provide the EXACT SKU. If the user provides a product name, use tool_search_product first to find the exact SKU."""
    return add_item_to_bill(ctx.deps.chat_id, sku, quantity)

@agent.tool
def tool_edit_bill_item(ctx: RunContext[AgentDeps], sku: str, new_quantity: float) -> str:
    """Edit the quantity of an item in the draft bill. Pass 0 to remove.
    IMPORTANT: You must provide the EXACT SKU."""
    return edit_bill_item(ctx.deps.chat_id, sku, new_quantity)

@agent.tool
def tool_view_bill(ctx: RunContext[AgentDeps]) -> str:
    """View the current draft bill and its totals."""
    return view_bill(ctx.deps.chat_id)

@agent.tool
def tool_cancel_bill(ctx: RunContext[AgentDeps]) -> str:
    """Cancel the current draft bill."""
    return cancel_bill(ctx.deps.chat_id)

@agent.tool
def tool_finalize_bill(ctx: RunContext[AgentDeps], payment_mode: str, customer_name: str, khata_customer: str = None) -> str:
    """Finalize the draft bill.
    payment_mode must be 'cash', 'upi', 'card', or 'khata'.
    customer_name is ALWAYS required — the name of the buyer. NEVER finalize without it. Ask if not provided.
    khata_customer is only needed when payment_mode is 'khata'."""
    # Use message_id as idempotency key
    txn_id = f"msg_{ctx.deps.message_id}"
    return finalize_bill(ctx.deps.chat_id, payment_mode, customer_name, khata_customer, txn_id)

# Register Khata Tools
@agent.tool
def tool_create_khata(ctx: RunContext[AgentDeps], customer_name: str) -> str:
    """Create a new khata (credit ledger) for a customer."""
    return create_khata(ctx.deps.chat_id, customer_name)

@agent.tool
def tool_charge_khata(ctx: RunContext[AgentDeps], customer_name: str, amount: float, note: str = "") -> str:
    """Add a manual charge to a customer's khata."""
    return charge_khata(ctx.deps.chat_id, customer_name, amount, note)

@agent.tool
def tool_pay_khata(ctx: RunContext[AgentDeps], customer_name: str, amount: float, note: str = "") -> str:
    """Record a payment received from a khata customer."""
    return pay_khata(ctx.deps.chat_id, customer_name, amount, note)

@agent.tool
def tool_check_khata(ctx: RunContext[AgentDeps], customer_name: str = None) -> str:
    """Check balance for a specific customer or list all khatas."""
    return check_khata(ctx.deps.chat_id, customer_name)

# Register Preferences Tools
@agent.tool
def tool_set_preference(ctx: RunContext[AgentDeps], key: str, value: str) -> str:
    """Set a preference for the owner (e.g. default_payment=upi, default_atta=aashirvaad 5kg)."""
    return set_preference(ctx.deps.chat_id, key, value)

# Register Document Tools
@agent.tool
def tool_generate_invoice_pdf(ctx: RunContext[AgentDeps], bill_id: int) -> str:
    """Generate a GST-compliant PDF invoice for a finalized bill."""
    return generate_invoice_pdf(ctx.deps.chat_id, bill_id)

@agent.tool
def tool_generate_analysis_pptx(ctx: RunContext[AgentDeps]) -> str:
    """Generate a weekly sales analysis PPTX deck."""
    return generate_analysis_pptx(ctx.deps.chat_id)

# Register Analytics Tools
@agent.tool
def tool_daily_summary(ctx: RunContext[AgentDeps], target_date: str = None) -> str:
    """Get the summary of today's sales (or a specific date YYYY-MM-DD)."""
    return daily_summary(ctx.deps.chat_id, target_date)

@agent.tool
def tool_close_day(ctx: RunContext[AgentDeps]) -> str:
    """Snapshot today's sales into the daily_close table."""
    return close_day(ctx.deps.chat_id)

