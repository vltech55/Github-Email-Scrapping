"""
Email template management for common email types.
"""

from typing import Dict, Any, Optional, List
import re


class EmailTemplateManager:
    """Manages email templates for common use cases."""
    
    def __init__(self):
        """Initialize with built-in templates."""
        self.templates = {
            'welcome': {
                'subject': 'Welcome to {service_name}!',
                'plain_text': """
Hello {user_name},

Welcome to {service_name}! We're excited to have you on board.

{welcome_message}

If you have any questions, feel free to reply to this email.

Best regards,
The {service_name} Team
                """.strip(),
                'html': """
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #2c5282;">Hello {user_name}!</h2>
        <p>Welcome to <strong>{service_name}</strong>! We're excited to have you on board.</p>
        
        {welcome_message_html}
        
        <p>If you have any questions, feel free to reply to this email.</p>
        
        <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e2e8f0;">
            <p><strong>Best regards,</strong><br>The {service_name} Team</p>
        </div>
    </div>
</body>
</html>
                """.strip()
            },
            
            'notification': {
                'subject': 'Notification: {title}',
                'plain_text': """
Hello {user_name},

{message}

{additional_info}

This is an automated notification from {service_name}.

Best regards,
The {service_name} Team
                """.strip(),
                'html': """
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #2c5282;">Notification: {title}</h2>
        <p>Hello {user_name},</p>
        
        <div style="background-color: #f7fafc; padding: 15px; border-left: 4px solid #3182ce; margin: 20px 0;">
            <p>{message}</p>
        </div>
        
        {additional_info_html}
        
        <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e2e8f0;">
            <p><em>This is an automated notification from {service_name}.</em></p>
            <p><strong>Best regards,</strong><br>The {service_name} Team</p>
        </div>
    </div>
</body>
</html>
                """.strip()
            },
            
            'password_reset': {
                'subject': 'Password Reset Request - {service_name}',
                'plain_text': """
Hello {user_name},

We received a request to reset your password for {service_name}.

If you made this request, click the link below to reset your password:
{reset_link}

This link will expire in {expiry_time}.

If you didn't request a password reset, please ignore this email or contact support if you have concerns.

Best regards,
The {service_name} Security Team
                """.strip(),
                'html': """
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #2c5282;">Password Reset Request</h2>
        <p>Hello {user_name},</p>
        
        <p>We received a request to reset your password for <strong>{service_name}</strong>.</p>
        
        <div style="text-align: center; margin: 30px 0;">
            <a href="{reset_link}" style="background-color: #3182ce; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block;">Reset Password</a>
        </div>
        
        <p><small>Or copy and paste this link: {reset_link}</small></p>
        
        <div style="background-color: #fed7d7; padding: 15px; border-left: 4px solid #e53e3e; margin: 20px 0;">
            <p><strong>Security Notice:</strong></p>
            <p>• This link expires in {expiry_time}</p>
            <p>• If you didn't request this reset, please ignore this email</p>
            <p>• Contact support if you have security concerns</p>
        </div>
        
        <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e2e8f0;">
            <p><strong>Best regards,</strong><br>The {service_name} Security Team</p>
        </div>
    </div>
</body>
</html>
                """.strip()
            },
            
            'order_confirmation': {
                'subject': 'Order Confirmation #{order_id} - {service_name}',
                'plain_text': """
Hello {customer_name},

Thank you for your order! Here are your order details:

Order #: {order_id}
Date: {order_date}
Total: {order_total}

Items:
{order_items}

Shipping Address:
{shipping_address}

Your order will be processed within 1-2 business days.

Thank you for choosing {service_name}!

Best regards,
The {service_name} Team
                """.strip(),
                'html': """
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #2c5282;">Order Confirmation</h2>
        <p>Hello {customer_name},</p>
        
        <p>Thank you for your order!</p>
        
        <div style="background-color: #f7fafc; padding: 20px; border-radius: 6px; margin: 20px 0;">
            <h3 style="margin-top: 0;">Order Details</h3>
            <p><strong>Order #:</strong> {order_id}</p>
            <p><strong>Date:</strong> {order_date}</p>
            <p><strong>Total:</strong> {order_total}</p>
        </div>
        
        <div style="margin: 20px 0;">
            <h3>Items Ordered</h3>
            <div style="background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px; padding: 15px;">
                {order_items_html}
            </div>
        </div>
        
        <div style="margin: 20px 0;">
            <h3>Shipping Address</h3>
            <div style="background-color: #f7fafc; padding: 15px; border-radius: 6px;">
                {shipping_address_html}
            </div>
        </div>
        
        <div style="background-color: #e6fffa; padding: 15px; border-left: 4px solid #38b2ac; margin: 20px 0;">
            <p><strong>Processing Time:</strong> Your order will be processed within 1-2 business days.</p>
        </div>
        
        <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e2e8f0;">
            <p>Thank you for choosing <strong>{service_name}</strong>!</p>
            <p><strong>Best regards,</strong><br>The {service_name} Team</p>
        </div>
    </div>
</body>
</html>
                """.strip()
            }
        }
    
    def get_template(self, template_name: str) -> Dict[str, str]:
        """
        Get a template by name.
        
        Args:
            template_name: Name of the template
            
        Returns:
            dict: Template with subject, plain_text, and html keys
            
        Raises:
            KeyError: If template doesn't exist
        """
        if template_name not in self.templates:
            available = ', '.join(self.templates.keys())
            raise KeyError(f"Template '{template_name}' not found. Available: {available}")
        
        return self.templates[template_name].copy()
    
    def add_template(self, name: str, subject: str, plain_text: str, html: str) -> None:
        """
        Add a custom template.
        
        Args:
            name: Template name
            subject: Email subject template
            plain_text: Plain text body template
            html: HTML body template
        """
        self.templates[name] = {
            'subject': subject,
            'plain_text': plain_text,
            'html': html
        }
    
    def list_templates(self) -> Dict[str, str]:
        """
        List all available templates.
        
        Returns:
            dict: Template names and their subjects
        """
        return {name: template['subject'] for name, template in self.templates.items()}
    
    def render_template(self, template_name: str, variables: Dict[str, Any]) -> Dict[str, str]:
        """
        Render a template with variables.
        
        Args:
            template_name: Name of the template to render
            variables: Variables to substitute in the template
            
        Returns:
            dict: Rendered template with subject, plain_text, and html
        """
        template = self.get_template(template_name)
        
        # Prepare variables for HTML vs plain text
        html_variables = self._prepare_html_variables(variables)
        
        rendered = {
            'subject': template['subject'].format(**variables),
            'plain_text': template['plain_text'].format(**variables),
            'html': template['html'].format(**html_variables)
        }
        
        return rendered
    
    def _prepare_html_variables(self, variables: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare variables for HTML rendering (escape HTML, format lists, etc.).
        
        Args:
            variables: Original variables
            
        Returns:
            dict: Variables prepared for HTML rendering
        """
        html_vars = variables.copy()
        
        # Convert plain text variables to HTML where needed
        for key, value in variables.items():
            if isinstance(value, str):
                # Convert newlines to <br> for HTML
                html_key = f"{key}_html"
                html_vars[html_key] = value.replace('\n', '<br>')
                
                # Handle lists (items separated by newlines)
                if '\n• ' in value or '\n- ' in value:
                    # Convert bullet lists to HTML
                    lines = value.split('\n')
                    html_list = '<ul>'
                    for line in lines:
                        if line.strip().startswith(('• ', '- ')):
                            html_list += f'<li>{line.strip()[2:]}</li>'
                        elif line.strip():
                            html_list += f'<p>{line.strip()}</p>'
                    html_list += '</ul>'
                    html_vars[html_key] = html_list
        
        return html_vars
    
    def create_plain_text_from_html(self, html_content: str) -> str:
        """
        Create a plain text version from HTML content.
        
        Args:
            html_content: HTML email content
            
        Returns:
            str: Plain text version
        """
        # Simple HTML to text conversion
        text = html_content
        
        # Remove script and style tags completely
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        
        # Convert common HTML elements
        text = re.sub(r'<br[^>]*>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'</p>', '\n\n', text, flags=re.IGNORECASE)
        text = re.sub(r'</div>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'</h[1-6]>', '\n\n', text, flags=re.IGNORECASE)
        
        # Remove remaining HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # Clean up whitespace
        text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)  # Multiple newlines to double
        text = re.sub(r'[ \t]+', ' ', text)  # Multiple spaces to single
        text = text.strip()
        
        return text


# Global template manager instance
template_manager = EmailTemplateManager()


def get_template(template_name: str) -> Dict[str, str]:
    """
    Get an email template by name.
    
    Args:
        template_name: Name of the template
        
    Returns:
        dict: Template with subject, plain_text, and html keys
    """
    return template_manager.get_template(template_name)


def render_template(template_name: str, **variables) -> Dict[str, str]:
    """
    Render a template with variables.
    
    Args:
        template_name: Name of the template to render
        **variables: Variables to substitute in the template
        
    Returns:
        dict: Rendered template with subject, plain_text, and html
    """
    return template_manager.render_template(template_name, variables)


def list_templates() -> Dict[str, str]:
    """
    List all available email templates.
    
    Returns:
        dict: Template names and their subjects
    """
    return template_manager.list_templates()


# Example template usage functions
def create_welcome_email(user_name: str, service_name: str, 
                        welcome_message: str = "") -> Dict[str, str]:
    """
    Create a welcome email using the welcome template.
    
    Args:
        user_name: Name of the user
        service_name: Name of the service/application
        welcome_message: Optional additional welcome message
        
    Returns:
        dict: Rendered welcome email template
    """
    variables = {
        'user_name': user_name,
        'service_name': service_name,
        'welcome_message': welcome_message or "We hope you enjoy using our service!"
    }
    
    return render_template('welcome', **variables)


def create_notification_email(user_name: str, title: str, message: str,
                            service_name: str, additional_info: str = "") -> Dict[str, str]:
    """
    Create a notification email using the notification template.
    
    Args:
        user_name: Name of the user
        title: Notification title
        message: Main notification message
        service_name: Name of the service/application
        additional_info: Optional additional information
        
    Returns:
        dict: Rendered notification email template
    """
    variables = {
        'user_name': user_name,
        'title': title,
        'message': message,
        'service_name': service_name,
        'additional_info': additional_info
    }
    
    return render_template('notification', **variables)


# Custom templates for GitHub user outreach (anti-spam rotation)
GITHUB_TEMPLATES = [
    # Template 1: Direct/Simple (Text-based straightforward message)
    {
        'subject': 'Quick Partnership Idea',
        'body': '''Hello.

I checked out your GitHub profile. It looks like you got the right skills for working together on something.

Let me just say it straight.

You are American. That means you can probably land good rates on places like Upwork and other freelance sites.

I plan to set up accounts using your name. That way I can grab projects and finish them up.

It will bring in some real revenue. I feel sure I can pull in $10k-20k a month. I will split part of that money with you. So you end up with extra cash without much effort.

Just reach out if this sounds good. Many Americans and Asians team up like this. They make money that way.

Thanks ahead of time.''',
        'html_body': '''<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto;">
    <div style="padding: 20px;">
        <p>Hello.</p>
        <p>I checked out your GitHub profile. It looks like you got the right skills for working together on something.</p>
        <p>Let me just say it straight.</p>
        <p>You are American. That means you can probably land good rates on places like Upwork and other freelance sites.</p>
        <p>I plan to set up accounts using your name. That way I can grab projects and finish them up.</p>
        <p>It will bring in some real revenue. I feel sure I can pull in $10k-20k a month. I will split part of that money with you. So you end up with extra cash without much effort.</p>
        <p>Just reach out if this sounds good. Many Americans and Asians team up like this. They make money that way.</p>
        <p>Thanks ahead of time.</p>
    </div>
</body>
</html>'''
    },
    
    # Template 2: Conversational/Friendly (Warmer tone, still comprehensive)
    {
        'subject': 'Partnership Idea: Upwork Collaboration with Solid Income Potential',
        'body': '''Hi there,

I hope this email finds you well! I came across your profile and wanted to reach out about a partnership opportunity that could create a meaningful income stream for you with relatively minimal time investment.

**Quick Background:**
I'm {sender_name}, a software engineer who's been building web applications, APIs, and full-stack solutions for clients for several years now. I've worked with everyone from early-stage startups to established companies, primarily in the US market. My technical background spans modern frameworks (React, Node.js, Python/Django, etc.) and I've successfully delivered dozens of projects.

**Here's the Situation:**
I had a thriving Upwork account that was generating consistent income until it got permanently banned. The frustrating part? It wasn't even my fault—a client shared contact info before we had a contract in place, which violated Upwork's terms. Despite explaining the situation, they won't reinstate the account.

Since then, I've been working with a few US-based partners in similar arrangements, and it's working really well for everyone involved. I handle all the technical work, they maintain the client relationship, and we both benefit from the higher rates that US-based profiles command.

**The Partnership Model (Simple & Fair):**

Here's how it typically works:

1. **Your Part (2-4 hours/week):**
   - Create an Upwork profile (I can help with this)
   - Join client video calls 1-2 times per week (usually 30-60 minutes each)
   - Quick review of project milestones before delivery (optional)

2. **My Part (All the heavy lifting):**
   - Find and apply to relevant projects daily
   - Write compelling proposals that win contracts
   - Handle all technical development, testing, and delivery
   - Provide you with call prep materials (bullet points, demos, FAQs)
   - Manage project timelines and client communication

3. **Revenue Split:**
   - We agree on a fair percentage (typically 30-40% for you, 60-70% for me)
   - Based on average project rates, you could see $2,000-$4,000/month passive income
   - Payments go through your Upwork account, then we split according to our agreement

**Why This Works:**

• **Location Premium:** US-based developers on Upwork typically charge $80-$200+/hour, while international developers with similar skills often get $30-$60/hour. It's primarily about client perception and location, not actual capability.

• **Win-Win Economics:** You get passive income for minimal time investment. I get access to better-paying clients. Clients get quality work delivered professionally.

• **Low Risk Start:** We can begin with a small trial project (maybe 10-20 hours) to validate we work well together before committing to anything larger.

• **Professional Setup:** I'll provide call preparation materials before every meeting, so you're never caught off-guard. I can also join calls as a "team member" if needed.

**Trust & Transparency:**

I completely get that this requires trust on both sides. Here's how we can build that:

- Start small with a trial project to test the workflow
- I can provide references from current partners (anonymously)
- Clear written agreement outlining everything
- You maintain full control of the Upwork account
- Either party can discontinue at any time

**Real Talk:**

This isn't a "get rich quick" scheme—it requires consistent work on my end and occasional time commitment on yours. But for several of my current partners, it's become a reliable $2-4k/month side income that fits around their schedule. One partner even scaled it to $6k/month after we built up a strong client base.

**Next Steps:**

If this sounds interesting, I'd love to hop on a quick 20-minute call to:
- Share more about my background and past projects
- Answer any questions you have
- Discuss the specifics of how we'd structure things
- See if we're a good fit to work together

I'm pretty flexible with timing—happy to work around your schedule. Just suggest a day/time that works for you, and I'll make it happen.

Thanks for reading through this! Looking forward to potentially working together.

Best,
{sender_name}

P.S. If this isn't your thing or the timing's not right, totally understand—just let me know and I won't follow up. No hard feelings!
''',
        'html_body': '''
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.7; color: #444; max-width: 600px; margin: 0 auto;">
    <div style="padding: 20px;">
        <h2 style="color: #38a169; margin-top: 0;">Hi there,</h2>
        <p>I’m <strong>{sender_name}</strong>, a software engineer focused on clear communication and reliable delivery. I typically handle the heavy lifting—finding work, writing proposals, and building features—while my US-based partner keeps a compliant Upwork profile and joins client calls when needed. We then split profits fairly.</p>
        <div style="background-color: #f0fff4; padding: 16px 18px; border-radius: 8px; margin: 18px 0;">
            <p style="margin: 0 0 6px 0;"><strong>Why this can work well</strong></p>
            <ul style="margin: 8px 0 0 18px;">
                <li>Leverage higher US rates with efficient delivery</li>
                <li>Call briefs, demos, and written updates to save your time</li>
                <li>Start with a small trial to validate fit</li>
            </ul>
        </div>
        <p style="margin-top: 16px;">If you’re open to exploring, I can share a short one-pager and propose a 15-minute intro to align expectations.</p>
        <p><strong>Would a quick call this or next week work for you?</strong></p>
        <div style="margin-top: 26px; padding-top: 14px; border-top: 1px solid #e2e8f0;">
            <p style="margin: 0 0 6px 0;">Best,</p>
            <p style="margin: 0;"><strong>{sender_name}</strong></p>
            <p style="margin: 8px 0 0 0; color: #718096; font-size: 12px;">If now isn’t a good time, reply “later” and I’ll follow up another time.</p>
        </div>
    </div>
</body>
</html>
'''
    },
    
    # Template 3: Executive/Direct (Professional and detailed, business-focused)
    {
        'subject': 'Business Proposal: Technical Partnership with Revenue Sharing',
        'body': '''Hello,

I'm reaching out with a straightforward business proposal that I believe could provide significant value to both of us. I'll keep this direct and detailed so you have all the information to make an informed decision.

**The Proposal:**
A technical partnership where I handle software development delivery while you maintain the client relationship through a US-based Upwork profile. Revenue is split based on a pre-agreed percentage.

**Background & Context:**
I'm {sender_name}, a software engineer with a track record of delivering full-stack applications, API integrations, and database solutions for US clients across SaaS, fintech, and e-commerce sectors. My previous Upwork account (which generated $80-150k annually) was permanently suspended due to a client's policy violation—they shared contact information before contract establishment, which Upwork considers grounds for permanent ban regardless of fault.

**Market Reality:**
There's a documented rate disparity on freelancing platforms: US-based developers command $80-$250+/hour while international developers with equivalent or superior technical skills typically receive $30-$60/hour. This gap is driven primarily by client perception and geographic bias rather than actual capability.

**Partnership Structure:**

**Your Responsibilities (2-4 hours weekly):**
• Maintain an Upwork profile (I can provide guidance on optimization)
• Participate in client video calls 1-2 times per week (30-60 minutes each)
• Brief review of major milestones before client delivery
• Transparent communication about project status

**My Responsibilities (Full-time commitment):**
• Daily project sourcing and proposal submission
• All technical development, testing, QA, and deployment
• Comprehensive call preparation materials (talking points, demos, technical documentation)
• Project management and timeline coordination
• Client communication management (technical questions, updates, scope discussions)

**Financial Model:**
• Revenue split: Negotiable, typically 30-40% to you, 60-70% to me
• Based on market rates and typical project velocity: $2,000-$5,000+ monthly for you
• Payments processed through your Upwork account with agreed-upon transfer schedule
• No upfront costs or investments required from you

**Risk Management & Trust Development:**

This arrangement requires mutual trust. Here's my proposed approach:

1. **Initial Trial Period:** Start with one small project (10-20 hours, $800-2,000 range) to validate compatibility
2. **Incremental Scaling:** Gradually increase project size as trust builds
3. **Written Agreement:** Clear documentation of responsibilities, revenue split, and termination clauses
4. **Reference Verification:** I can provide contact with current partners (with their permission)
5. **Account Control:** You maintain full control and ownership of the Upwork profile
6. **Flexible Commitment:** Either party can exit the arrangement with 30 days notice

**Why This Works Long-Term:**

This isn't a quick arbitrage play—it's a sustainable business model:

• **Client Quality:** US-based profiles attract higher-quality, better-paying clients
• **Established Process:** I've refined this workflow with multiple partners over 2+ years
• **Scalability:** As reputation builds, hourly rates and project values increase
• **Consistency:** Regular income stream that can supplement or eventually replace primary income

**Real Performance Data:**

Current partnerships (anonymized):
• Partner A: $2,800/month average, 3 hours/week commitment, 8 months duration
• Partner B: $4,200/month average, 4 hours/week commitment, 14 months duration
• Partner C: $6,100/month average, 5 hours/week commitment, 22 months duration (scaled significantly)

These are actual numbers, not projections. Your results would depend on market conditions, project availability, and how much time we invest in profile optimization.

**Technical Capabilities I Bring:**

• Full-stack development (React, Vue.js, Node.js, Python/Django, PHP)
• Database design and optimization (PostgreSQL, MySQL, MongoDB)
• API development and third-party integrations
• Cloud infrastructure (AWS, Google Cloud, DigitalOcean)
• Mobile app development (React Native)
• DevOps and deployment automation

**Next Steps:**

If this aligns with your business goals, I propose a 25-minute video call where we can:

1. I'll share screen recordings of past projects and current work
2. Review the partnership agreement template
3. Discuss specific terms and revenue split
4. Address any concerns or questions you have
5. Determine mutual fit and next steps

I'm available for calls throughout the week and can accommodate your schedule. Please suggest 2-3 time slots that work for you, and I'll confirm one immediately.

**Due Diligence:**

I encourage you to:
• Research this partnership model (it's increasingly common in the freelancing space)
• Consider the time commitment and whether it fits your schedule
• Evaluate the financial opportunity against your other income sources
• Ask any questions before committing to even the initial call

Thank you for considering this proposal. I look forward to the possibility of building a mutually beneficial, long-term partnership.

Best regards,
{sender_name}

---

P.S. If this doesn't align with your current goals or interests, I completely understand—just reply with "not interested" and I'll remove you from any future outreach. I respect your time and decision either way.
''',
        'html_body': '''
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #2d3748; max-width: 620px; margin: 0 auto; background-color: #f7fafc;">
    <div style="padding: 24px; background-color: white; border: 1px solid #e2e8f0;">
        <h2 style="color: #1a202c; margin: 0 0 12px 0;">Hello,</h2>
        <p style="margin: 0 0 14px 0;">Here’s a concise partnership model that keeps things simple and fair:</p>
        <ul style="margin: 0 0 16px 18px;">
            <li><strong>You</strong>: Host an Upwork profile and join client calls when needed</li>
            <li><strong>Me</strong>: Find opportunities, write proposals, and deliver the development work</li>
            <li><strong>Split</strong>: Agree on a transparent percentage of profits</li>
        </ul>
        <div style="background: #edf2f7; padding: 14px 16px; border-radius: 6px; margin: 18px 0;">
            <p style="margin: 0;"><strong>Rationale</strong></p>
            <ul style="margin: 8px 0 0 18px;">
                <li>US-based profiles typically earn higher hourly rates ($80–$250+/hr)</li>
                <li>Clear division of responsibilities and time commitment</li>
                <li>Start with a small pilot to validate fit and trust</li>
            </ul>
        </div>
        <p style="margin: 0 0 12px 0;"><strong>If this aligns with your goals, would a brief 10–15 minute intro work?</strong></p>
        <div style="margin-top: 20px; padding-top: 14px; border-top: 1px solid #e2e8f0;">
            <p style="margin: 0 0 6px 0;">Regards,</p>
            <p style="margin: 0;"><strong>{sender_name}</strong></p>
            <p style="margin: 8px 0 0 0; color: #718096; font-size: 12px;">No problem if not interested—just reply and I’ll stop following up.</p>
        </div>
    </div>
</body>
</html>
'''
    }
]


def get_rotating_template(index: int) -> Dict[str, str]:
    """
    Get template by index for rotation.
    
    Args:
        index: Template index (0, 1, or 2)
        
    Returns:
        dict: Template with subject, body, and html_body
    """
    return GITHUB_TEMPLATES[index % len(GITHUB_TEMPLATES)]


def list_github_templates() -> List[str]:
    """
    List all GitHub outreach templates.
    
    Returns:
        list: Template descriptions
    """
    return [
        "Professional/Formal style",
        "Casual/Friendly style",
        "Technical/Developer style"
    ]
