"""Email template generators for MetroScope verification, daily newsletter, and unsubscribe."""

import html
from typing import Any, Dict, List, Tuple


def _html_escape(text: str) -> str:
    """Safely escapes HTML special characters."""
    return html.escape(text or "")


def render_verification_email(email: str, verify_url: str) -> Tuple[str, str]:
    """Generates double opt-in verification email (HTML and plain text)."""
    escaped_email = _html_escape(email)
    escaped_url = _html_escape(verify_url)

    text_body = f"""Confirm your MetroScope Newsletter Subscription

Hello,

Thank you for requesting to receive the MetroScope Daily Briefing.

To verify your email address and activate your free subscription, please visit the link below:

{verify_url}

This link is valid for 24 hours. If you did not request this subscription, please ignore this email.

---
MetroScope News | Automated US & Global News Discovery
https://themetroscope.com
"""

    html_body = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Confirm Your Subscription - MetroScope</title>
</head>
<body style="margin: 0; padding: 0; background-color: #F8FAFC; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1E293B; -webkit-font-smoothing: antialiased;">
  <table role="presentation" width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color: #F8FAFC; padding: 32px 16px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" border="0" cellspacing="0" cellpadding="0" style="max-width: 580px; background-color: #FFFFFF; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -2px rgba(0, 0, 0, 0.05); border: 1px solid #E2E8F0;">
          <!-- Header -->
          <tr>
            <td style="background-color: #0B192C; padding: 28px 32px; text-align: left;">
              <span style="font-size: 24px; font-weight: 800; letter-spacing: -0.025em; color: #FFFFFF;">METRO<span style="color: #E5A93C;">SCOPE</span></span>
              <p style="margin: 4px 0 0 0; font-size: 13px; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.05em;">Curated Daily News Intelligence</p>
            </td>
          </tr>
          <!-- Body -->
          <tr>
            <td style="padding: 36px 32px;">
              <h1 style="margin: 0 0 16px 0; font-size: 20px; font-weight: 700; color: #0B192C;">Confirm your email subscription</h1>
              <p style="margin: 0 0 20px 0; font-size: 15px; line-height: 1.6; color: #475569;">
                Thank you for signing up to receive the MetroScope Daily Briefing. To activate your subscription for <strong>{escaped_email}</strong>, please confirm below.
              </p>
              <table role="presentation" border="0" cellspacing="0" cellpadding="0" style="margin: 28px 0;">
                <tr>
                  <td align="center" style="border-radius: 6px; background-color: #0B192C;">
                    <a href="{escaped_url}" target="_blank" style="display: inline-block; padding: 14px 28px; font-size: 15px; font-weight: 600; color: #FFFFFF; text-decoration: none; border-radius: 6px; background-color: #0B192C; border: 1px solid #1E293B;">
                      Confirm Subscription
                    </a>
                  </td>
                </tr>
              </table>
              <p style="margin: 0 0 12px 0; font-size: 13px; line-height: 1.5; color: #64748B;">
                Or copy and paste this link into your browser:<br>
                <a href="{escaped_url}" style="color: #2563EB; word-break: break-all; font-size: 12px;">{escaped_url}</a>
              </p>
              <p style="margin: 24px 0 0 0; font-size: 13px; color: #94A3B8;">
                This link expires in 24 hours. If you did not request this subscription, no further action is required.
              </p>
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="background-color: #F1F5F9; padding: 20px 32px; text-align: center; font-size: 12px; color: #64748B; border-top: 1px solid #E2E8F0;">
              &copy; MetroScope News. Real-time news discovery and automated intelligence.
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""
    return html_body, text_body


def render_newsletter_email(
    campaign_date: str,
    articles: List[Dict[str, Any]],
    unsubscribe_url: str,
) -> Tuple[str, str]:
    """Generates responsive daily briefing newsletter email (HTML and plain text)."""
    escaped_date = _html_escape(campaign_date)
    escaped_unsub_url = _html_escape(unsubscribe_url)

    # Build plain text representation
    text_lines = [
        f"METROSCOPE DAILY BRIEFING — {campaign_date}",
        "Top curated US and global news stories",
        "=" * 48,
        "",
    ]
    for idx, art in enumerate(articles, 1):
        title = art.get("title", "")
        category = art.get("category", "General")
        source = art.get("source", "MetroScope")
        url = art.get("url", "")
        summary = art.get("summary", "")
        text_lines.append(f"{idx}. [{category.upper()}] {title}")
        text_lines.append(f"   Source: {source}")
        if summary:
            text_lines.append(f"   {summary}")
        text_lines.append(f"   Read: {url}")
        text_lines.append("")

    text_lines.extend(
        [
            "-" * 48,
            "You received this briefing because you subscribed to MetroScope News.",
            f"To unsubscribe at any time: {unsubscribe_url}",
            "MetroScope News | https://themetroscope.com",
        ]
    )
    text_body = "\n".join(text_lines)

    # Build HTML articles section
    article_cards = []
    for art in articles:
        title = _html_escape(art.get("title", ""))
        category = _html_escape(art.get("category", "General"))
        source = _html_escape(art.get("source", "MetroScope"))
        url = _html_escape(art.get("url", ""))
        summary = _html_escape(art.get("summary", ""))

        card_html = f"""
        <div style="padding: 20px 0; border-bottom: 1px solid #E2E8F0;">
          <div style="margin-bottom: 6px;">
            <span style="display: inline-block; background-color: #E2E8F0; color: #0B192C; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; padding: 2px 8px; border-radius: 4px;">{category}</span>
            <span style="font-size: 12px; color: #64748B; margin-left: 8px;">{source}</span>
          </div>
          <h2 style="margin: 0 0 8px 0; font-size: 17px; line-height: 1.4; font-weight: 700;">
            <a href="{url}" target="_blank" style="color: #0B192C; text-decoration: none;">{title}</a>
          </h2>
          {f'<p style="margin: 0 0 10px 0; font-size: 14px; line-height: 1.5; color: #475569;">{summary}</p>' if summary else ''}
          <a href="{url}" target="_blank" style="font-size: 13px; font-weight: 600; color: #2563EB; text-decoration: none;">Read full story &rarr;</a>
        </div>
        """
        article_cards.append(card_html)

    articles_content = "".join(article_cards)

    html_body = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>MetroScope Daily Briefing - {escaped_date}</title>
</head>
<body style="margin: 0; padding: 0; background-color: #F8FAFC; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1E293B; -webkit-font-smoothing: antialiased;">
  <table role="presentation" width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color: #F8FAFC; padding: 24px 16px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" border="0" cellspacing="0" cellpadding="0" style="max-width: 600px; background-color: #FFFFFF; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); border: 1px solid #E2E8F0;">
          <!-- Header -->
          <tr>
            <td style="background-color: #0B192C; padding: 28px 32px;">
              <span style="font-size: 24px; font-weight: 800; letter-spacing: -0.025em; color: #FFFFFF;">METRO<span style="color: #E5A93C;">SCOPE</span></span>
              <p style="margin: 6px 0 0 0; font-size: 13px; color: #CBD5E1; letter-spacing: 0.02em;">Daily News Briefing &bull; {escaped_date}</p>
            </td>
          </tr>
          <!-- Content -->
          <tr>
            <td style="padding: 24px 32px;">
              <p style="margin: 0 0 16px 0; font-size: 14px; color: #64748B;">
                Here is your curated briefing of the highest-impact stories discovered across verified news publishers today.
              </p>
              {articles_content}
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="background-color: #F1F5F9; padding: 24px 32px; text-align: center; font-size: 12px; color: #64748B; border-top: 1px solid #E2E8F0;">
              <p style="margin: 0 0 8px 0;">You received this briefing because you subscribed to MetroScope News.</p>
              <p style="margin: 0 0 12px 0;">
                <a href="{escaped_unsub_url}" style="color: #64748B; text-decoration: underline;">Unsubscribe from this newsletter</a>
                &bull;
                <a href="https://themetroscope.com/privacy" style="color: #64748B; text-decoration: underline;">Privacy Policy</a>
              </p>
              <p style="margin: 0; font-size: 11px; color: #94A3B8;">&copy; MetroScope News. All rights reserved.</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""
    return html_body, text_body


def render_unsubscribe_confirmation_email(email: str) -> Tuple[str, str]:
    """Generates confirmation message upon successful unsubscription."""
    escaped_email = _html_escape(email)

    text_body = f"""You have been unsubscribed from MetroScope

Hello,

The email address {email} has been successfully unsubscribed from the MetroScope Daily Briefing. You will not receive any further automated newsletter emails from us.

If this was a mistake, you can re-subscribe at any time on our website:
https://themetroscope.com

---
MetroScope News
"""

    html_body = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Unsubscribed - MetroScope</title>
</head>
<body style="margin: 0; padding: 0; background-color: #F8FAFC; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1E293B;">
  <table role="presentation" width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color: #F8FAFC; padding: 32px 16px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" border="0" cellspacing="0" cellpadding="0" style="max-width: 580px; background-color: #FFFFFF; border-radius: 8px; overflow: hidden; border: 1px solid #E2E8F0;">
          <tr>
            <td style="background-color: #0B192C; padding: 24px 32px;">
              <span style="font-size: 22px; font-weight: 800; color: #FFFFFF;">METRO<span style="color: #E5A93C;">SCOPE</span></span>
            </td>
          </tr>
          <tr>
            <td style="padding: 32px;">
              <h1 style="margin: 0 0 12px 0; font-size: 18px; font-weight: 700; color: #0B192C;">You have been unsubscribed</h1>
              <p style="margin: 0 0 16px 0; font-size: 14px; line-height: 1.6; color: #475569;">
                <strong>{escaped_email}</strong> has been removed from the MetroScope Daily Briefing list. You will no longer receive newsletter emails.
              </p>
              <p style="margin: 0; font-size: 13px; color: #64748B;">
                You can always re-subscribe at <a href="https://themetroscope.com" style="color: #2563EB;">themetroscope.com</a>.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""
    return html_body, text_body
