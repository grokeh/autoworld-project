"""
AutoWorld AI Service
Handles all Groq LLM interactions for the chatbot and admin insights.
"""

import json
from django.conf import settings

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False


def get_groq_client():
    if not GROQ_AVAILABLE:
        return None
    key = getattr(settings, 'GROQ_API_KEY', '')
    if not key or key == 'your-groq-api-key-here':
        return None
    return Groq(api_key=key)


def build_system_prompt(context_data: dict) -> str:
    """Build a system prompt with live AutoWorld data."""
    return f"""You are AutoWorld AI Assistant — a helpful, friendly assistant for AutoWorld, 
an AI-enhanced automotive marketplace in Nairobi, Kenya.

You help customers with:
- Finding and recommending vehicles
- Spare parts advice and compatibility
- Booking mechanics
- Order and payment questions
- General automotive advice

Current AutoWorld inventory snapshot:
- Vehicles available: {context_data.get('vehicle_count', 0)}
- Spare parts available: {context_data.get('sparepart_count', 0)}
- Certified mechanics: {context_data.get('mechanic_count', 0)}

Popular vehicle brands: {', '.join(context_data.get('brands', []))}
Available mechanic specializations: {', '.join(context_data.get('specializations', []))}

Rules:
- Keep responses concise and helpful (2-4 sentences max unless asked for detail)
- Always be friendly and professional
- If asked about prices, mention they are in KES (Kenyan Shillings)
- If you don't know something specific, suggest the user browse the relevant section
- Never make up specific prices or availability — direct users to browse the site
- You are NOT a general AI — stay focused on automotive and AutoWorld topics
"""


def get_context_data() -> dict:
    """Fetch live data from the database for the AI context."""
    try:
        from ecommerceapp.models import Vehicle, SparePart, Mechanic
        brands = list(Vehicle.objects.values_list('brand', flat=True).distinct()[:10])
        specs = list(Mechanic.objects.values_list('specialization', flat=True).distinct()[:8])
        return {
            'vehicle_count': Vehicle.objects.count(),
            'sparepart_count': SparePart.objects.count(),
            'mechanic_count': Mechanic.objects.count(),
            'brands': brands,
            'specializations': specs,
        }
    except Exception:
        return {
            'vehicle_count': 0,
            'sparepart_count': 0,
            'mechanic_count': 0,
            'brands': [],
            'specializations': [],
        }


def chat_with_ai(messages: list, user_message: str) -> str:
    """
    Send a message to Groq and return the response.
    messages: list of {'role': 'user'|'assistant', 'content': str}
    """
    client = get_groq_client()

    if not client:
        # Fallback rule-based responses when no API key
        return rule_based_response(user_message)

    try:
        context = get_context_data()
        system_prompt = build_system_prompt(context)

        groq_messages = [{'role': 'system', 'content': system_prompt}]
        # Keep last 6 messages for context
        groq_messages += messages[-6:]
        groq_messages.append({'role': 'user', 'content': user_message})

        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=groq_messages,
            max_tokens=512,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        return f"I'm having trouble connecting right now. Please try again shortly. ({str(e)[:60]})"


def rule_based_response(message: str) -> str:
    """Simple rule-based fallback when no API key is configured."""
    msg = message.lower()

    if any(w in msg for w in ['vehicle', 'car', 'buy', 'purchase']):
        return "We have a great selection of vehicles! Browse our catalogue at /vehicles/ to find the perfect match for your budget and needs."
    elif any(w in msg for w in ['spare', 'part', 'filter', 'brake', 'tyre']):
        return "We stock a wide range of genuine spare parts. Visit /spareparts/ to search by name or compatible vehicle."
    elif any(w in msg for w in ['mechanic', 'repair', 'service', 'book']):
        return "Our certified mechanics are ready to help! Go to /mechanics/ to find one near you and book an appointment."
    elif any(w in msg for w in ['price', 'cost', 'how much', 'kes']):
        return "Prices vary by product. Browse our vehicles or spare parts pages for current pricing in KES."
    elif any(w in msg for w in ['payment', 'mpesa', 'pay', 'checkout']):
        return "We accept M-Pesa, Stripe (card), PayPal, and Cash on Delivery. You can choose your preferred method at checkout."
    elif any(w in msg for w in ['hello', 'hi', 'hey', 'help']):
        return "Hello! 👋 I'm the AutoWorld AI Assistant. I can help you find vehicles, spare parts, or book a mechanic. What do you need?"
    elif any(w in msg for w in ['cancel', 'reschedule', 'booking']):
        return "You can manage your bookings from your dashboard under 'My Bookings'. You can cancel or reschedule pending bookings there."
    else:
        return "I'm here to help with vehicles, spare parts, mechanics, and bookings. What can I assist you with today?"


def generate_admin_insights() -> dict:
    """Generate AI-powered insights for the admin dashboard."""
    client = get_groq_client()

    try:
        from ecommerceapp.models import Vehicle, SparePart, Mechanic, Booking, Order
        from django.utils import timezone
        from datetime import timedelta

        today = timezone.now().date()
        week_ago = today - timedelta(days=7)

        stats = {
            'total_vehicles': Vehicle.objects.count(),
            'total_spareparts': SparePart.objects.count(),
            'total_mechanics': Mechanic.objects.count(),
            'bookings_this_week': Booking.objects.filter(created_at__date__gte=week_ago).count(),
            'pending_bookings': Booking.objects.filter(status='Pending').count(),
            'unpaid_bookings': Booking.objects.filter(is_paid=False, status='Pending').count(),
            'total_orders': Order.objects.count(),
            'pending_orders': Order.objects.filter(status='PENDING').count(),
        }

        if not client:
            # Rule-based insights
            insights = []
            if stats['pending_bookings'] > 5:
                insights.append(f"⚠️ {stats['pending_bookings']} bookings are pending approval.")
            if stats['unpaid_bookings'] > 3:
                insights.append(f"💳 {stats['unpaid_bookings']} bookings have unpaid deposits.")
            if stats['pending_orders'] > 0:
                insights.append(f"📦 {stats['pending_orders']} orders are awaiting processing.")
            if not insights:
                insights.append("✅ Operations are running smoothly. No critical issues detected.")
            return {'summary': ' '.join(insights), 'stats': stats}

        prompt = f"""You are an AI analyst for AutoWorld automotive workshop.
Analyze this data and give a 2-3 sentence operational summary with actionable insights:

- Vehicles in catalogue: {stats['total_vehicles']}
- Spare parts: {stats['total_spareparts']}
- Mechanics: {stats['total_mechanics']}
- Bookings this week: {stats['bookings_this_week']}
- Pending bookings: {stats['pending_bookings']}
- Unpaid booking deposits: {stats['unpaid_bookings']}
- Total orders: {stats['total_orders']}
- Pending orders: {stats['pending_orders']}

Be concise, professional, and highlight any concerns or opportunities."""

        response = client.chat.completions.create(
            model=getattr(settings, 'GROQ_MODEL_SMART', settings.GROQ_MODEL),
            messages=[{'role': 'user', 'content': prompt}],
            max_tokens=200,
            temperature=0.5,
        )
        summary = response.choices[0].message.content.strip()
        return {'summary': summary, 'stats': stats}

    except Exception as e:
        return {
            'summary': f'AI insights temporarily unavailable. ({str(e)[:60]})',
            'stats': {}
        }


# ─── Vehicle Image Analysis ───────────────────────────────────────────────────

import base64


def analyze_vehicle_image(image_file) -> dict:
    """
    Analyse a vehicle image using Groq vision model.
    Returns diagnosis, severity, recommended services, and suggested mechanic specializations.
    """
    client = get_groq_client()

    # Read and encode image
    try:
        image_data = image_file.read()
        image_b64  = base64.b64encode(image_data).decode('utf-8')
        mime_type  = getattr(image_file, 'content_type', 'image/jpeg')
    except Exception as e:
        return {'error': f'Could not read image: {str(e)}'}

    if not client:
        return {
            'diagnosis': 'AI analysis unavailable — Groq API key not configured.',
            'severity': 'unknown',
            'issues': [],
            'recommended_services': [],
            'mechanic_specializations': [],
            'urgency': 'unknown',
        }

    prompt = """You are an expert automotive technician AI for AutoWorld workshop in Nairobi, Kenya.

Analyse this vehicle image and provide:
1. What visible damage, wear, or issues you can see
2. Severity level: minor / moderate / severe / critical
3. Urgency: can_wait / book_soon / urgent / emergency
4. List of specific issues (max 5)
5. Recommended services from: Repair, Maintenance, Inspection, Other
6. Mechanic specializations needed

Respond in this exact JSON format:
{
  "diagnosis": "Brief overall assessment",
  "severity": "minor|moderate|severe|critical",
  "urgency": "can_wait|book_soon|urgent|emergency",
  "issues": ["issue 1", "issue 2"],
  "recommended_services": ["Repair", "Inspection"],
  "mechanic_specializations": ["Engine Repair", "Body Work"],
  "advice": "One sentence of practical advice for the owner"
}

If the image is not a vehicle or is unclear, respond with:
{"error": "Could not analyse image — please upload a clear photo of your vehicle"}"""

    try:
        response = client.chat.completions.create(
            model='meta-llama/llama-4-scout-17b-16e-instruct',
            messages=[{
                'role': 'user',
                'content': [
                    {
                        'type': 'image_url',
                        'image_url': {
                            'url': f'data:{mime_type};base64,{image_b64}'
                        }
                    },
                    {
                        'type': 'text',
                        'text': prompt
                    }
                ]
            }],
            max_tokens=600,
            temperature=0.3,
        )

        content = response.choices[0].message.content.strip()

        # Extract JSON from response
        import json, re
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            return result
        else:
            return {'diagnosis': content, 'severity': 'unknown', 'issues': [],
                    'recommended_services': [], 'mechanic_specializations': [],
                    'urgency': 'unknown', 'advice': ''}

    except Exception as e:
        return {
            'diagnosis': f'Analysis failed: {str(e)[:100]}',
            'severity': 'unknown',
            'issues': [],
            'recommended_services': [],
            'mechanic_specializations': [],
            'urgency': 'unknown',
        }
