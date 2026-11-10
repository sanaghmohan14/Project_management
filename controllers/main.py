# -*- coding: utf-8 -*-
from markupsafe import Markup
from odoo import http, fields, _
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)


class ProjectCustomerReviewController(http.Controller):

    def _validate_project_token(self, project_id, token):
        """Validate project exists and token matches."""
        project = request.env['project.manage'].sudo().browse(project_id)
        if not project.exists():
            return None, "Project not found."
        # If project has an access_token, it must match
        if project.access_token and token != project.access_token:
            return None, "Invalid or expired review link."
        return project, None

    @http.route(['/project/review/<int:project_id>'], type='http', auth='public', website=False, methods=['GET'])
    def customer_review_page(self, project_id, token=None, **kwargs):
        """Display the customer review submission form."""
        project, err = self._validate_project_token(project_id, token)
        if err or not project:
            return request.make_response(f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8"/>
                <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
                <title>Invalid Review Link</title>
                <style>
                    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #f8fafc; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; padding: 20px; box-sizing: border-box; }}
                    .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 36px; max-width: 480px; text-align: center; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.5); }}
                    h2 {{ color: #ef4444; margin: 0 0 12px; font-size: 22px; }}
                    p {{ color: #94a3b8; font-size: 14px; line-height: 1.6; margin: 0 0 20px; }}
                </style>
            </head>
            <body>
                <div class="card">
                    <h2>⚠️ {err}</h2>
                    <p>The feedback link you followed may be invalid or expired. Please contact your Project Manager for an updated link.</p>
                </div>
            </body>
            </html>
            """, headers=[('Content-Type', 'text/html')])

        is_completed = bool(project.state == 'done' or project.progress >= 100)
        client_name = project.partner_id.name or 'Valued Client'
        client_email = project.partner_id.email or ''
        client_phone = project.partner_id.phone or ''
        default_title = f"{'Completion Sign-Off Review' if is_completed else 'Milestone Feedback'} - {client_name}"
        progress_pct = int(project.progress)
        company_name = project.company_id.name or 'Benac Business Solutions'

        html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8"/>
            <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
            <title>Customer Review &amp; Feedback - {project.name}</title>
            <style>
                :root {{
                    --primary: #2563eb;
                    --primary-hover: #1d4ed8;
                    --gold: #f59e0b;
                    --bg: #0b0f19;
                    --card-bg: #111827;
                    --card-inner: #162032;
                    --border: #243042;
                    --text: #f8fafc;
                    --text-muted: #94a3b8;
                }}
                * {{ box-sizing: border-box; margin: 0; padding: 0; }}
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                    background: var(--bg);
                    color: var(--text);
                    padding: 30px 16px 60px;
                    line-height: 1.5;
                }}
                .container {{
                    max-width: 680px;
                    margin: 0 auto;
                }}
                .header-logo {{
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    gap: 12px;
                    margin-bottom: 24px;
                }}
                .logo-badge {{
                    background: #1e3a8a;
                    color: #ffffff;
                    font-weight: 800;
                    font-size: 20px;
                    width: 44px;
                    height: 44px;
                    border-radius: 10px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }}
                .company-name {{
                    font-size: 20px;
                    font-weight: 700;
                    color: #ffffff;
                }}
                .review-card {{
                    background: var(--card-bg);
                    border: 1px solid var(--border);
                    border-radius: 16px;
                    overflow: hidden;
                    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7);
                }}
                .card-header {{
                    background: linear-gradient(135deg, #1e3a8a 0%, #2563eb 100%);
                    padding: 24px 28px;
                    color: #ffffff;
                }}
                .card-header-tag {{
                    font-size: 11px;
                    text-transform: uppercase;
                    letter-spacing: 0.08em;
                    background: rgba(255, 255, 255, 0.2);
                    padding: 4px 10px;
                    border-radius: 20px;
                    font-weight: 700;
                    display: inline-block;
                    margin-bottom: 8px;
                }}
                .card-header h1 {{
                    font-size: 22px;
                    font-weight: 800;
                    margin-bottom: 4px;
                }}
                .card-header p {{
                    font-size: 13px;
                    opacity: 0.9;
                }}
                .project-summary {{
                    background: var(--card-inner);
                    padding: 16px 28px;
                    border-bottom: 1px solid var(--border);
                    display: flex;
                    flex-wrap: wrap;
                    justify-content: space-between;
                    gap: 12px;
                    font-size: 13px;
                }}
                .summary-item {{
                    display: flex;
                    flex-direction: column;
                }}
                .summary-label {{
                    color: var(--text-muted);
                    font-size: 11px;
                    text-transform: uppercase;
                    font-weight: 600;
                }}
                .summary-value {{
                    color: #ffffff;
                    font-weight: 700;
                    margin-top: 2px;
                }}
                .card-body {{
                    padding: 28px;
                }}
                .form-group {{
                    margin-bottom: 22px;
                }}
                label {{
                    display: block;
                    font-size: 13px;
                    font-weight: 600;
                    color: #cbd5e1;
                    margin-bottom: 8px;
                    text-transform: uppercase;
                    letter-spacing: 0.04em;
                }}
                label span.req {{
                    color: #ef4444;
                }}
                /* Star Rating */
                .rating-container {{
                    background: var(--card-inner);
                    border: 1px solid var(--border);
                    border-radius: 12px;
                    padding: 18px;
                    text-align: center;
                }}
                .star-group {{
                    display: inline-flex;
                    gap: 8px;
                    font-size: 34px;
                    cursor: pointer;
                    user-select: none;
                }}
                .star {{
                    color: #334155;
                    transition: all 0.15s ease;
                }}
                .star.active {{
                    color: var(--gold);
                    transform: scale(1.1);
                }}
                .star:hover {{
                    color: var(--gold);
                }}
                .rating-label {{
                    font-size: 14px;
                    font-weight: 700;
                    color: var(--gold);
                    margin-top: 8px;
                }}
                /* NPS Score */
                .nps-group {{
                    display: flex;
                    gap: 6px;
                    flex-wrap: wrap;
                }}
                .nps-btn {{
                    flex: 1;
                    min-width: 38px;
                    height: 38px;
                    background: var(--card-inner);
                    border: 1px solid var(--border);
                    border-radius: 6px;
                    color: var(--text);
                    font-weight: 600;
                    font-size: 13px;
                    cursor: pointer;
                    transition: all 0.15s ease;
                }}
                .nps-btn:hover, .nps-btn.active {{
                    background: var(--primary);
                    border-color: var(--primary);
                    color: #ffffff;
                }}
                .nps-subtext {{
                    display: flex;
                    justify-content: space-between;
                    font-size: 11px;
                    color: var(--text-muted);
                    margin-top: 6px;
                }}
                /* Form Inputs */
                input[type="text"], input[type="email"], input[type="tel"], select, textarea {{
                    width: 100%;
                    background: var(--card-inner);
                    border: 1px solid var(--border);
                    border-radius: 8px;
                    padding: 10px 14px;
                    color: #ffffff;
                    font-size: 14px;
                    font-family: inherit;
                    transition: border-color 0.15s ease;
                }}
                input:focus, select:focus, textarea:focus {{
                    outline: none;
                    border-color: var(--primary);
                    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.25);
                }}
                textarea {{
                    resize: vertical;
                    min-height: 85px;
                }}
                .row-2 {{
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 16px;
                }}
                @media (max-width: 600px) {{
                    .row-2 {{ grid-template-columns: 1fr; }}
                }}
                /* Submit Button */
                .submit-btn {{
                    width: 100%;
                    background: var(--primary);
                    color: #ffffff;
                    font-weight: 700;
                    font-size: 16px;
                    padding: 14px;
                    border: none;
                    border-radius: 10px;
                    cursor: pointer;
                    transition: all 0.15s ease;
                    margin-top: 10px;
                    box-shadow: 0 4px 6px -1px rgba(37, 99, 235, 0.4);
                }}
                .submit-btn:hover {{
                    background: var(--primary-hover);
                    transform: translateY(-1px);
                    box-shadow: 0 6px 10px -1px rgba(37, 99, 235, 0.5);
                }}
                .footer-text {{
                    text-align: center;
                    font-size: 12px;
                    color: var(--text-muted);
                    margin-top: 20px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header-logo">
                    <div class="logo-badge">B</div>
                    <div class="company-name">{company_name}</div>
                </div>

                <div class="review-card">
                    <div class="card-header">
                        <span class="card-header-tag">Customer Review &amp; Feedback</span>
                        <h1>{project.name}</h1>
                        <p>{'Final Project Completion Review' if is_completed else 'Project Progress & Milestone Feedback'}</p>
                    </div>

                    <div class="project-summary">
                        <div class="summary-item">
                            <span class="summary-label">Client</span>
                            <span class="summary-value">{client_name}</span>
                        </div>
                        <div class="summary-item">
                            <span class="summary-label">Progress</span>
                            <span class="summary-value" style="color: #60a5fa;">{progress_pct}%</span>
                        </div>
                        <div class="summary-item">
                            <span class="summary-label">Project Manager</span>
                            <span class="summary-value">{project.manager_id.name or 'Benac Team'}</span>
                        </div>
                        <div class="summary-item">
                            <span class="summary-label">Team Lead</span>
                            <span class="summary-value">{project.team_lead_id.name or 'Benac Team'}</span>
                        </div>
                    </div>

                    <form class="card-body" method="POST" action="/project/review/{project.id}/submit">
                        <input type="hidden" name="token" value="{token or ''}"/>
                        <input type="hidden" name="rating" id="ratingInput" value="5"/>
                        <input type="hidden" name="nps_score" id="npsInput" value="10"/>

                        <!-- Star Rating -->
                        <div class="form-group">
                            <label>Overall Delivery Rating <span class="req">*</span></label>
                            <div class="rating-container">
                                <div class="star-group" id="starGroup">
                                    <span class="star active" data-val="1">★</span>
                                    <span class="star active" data-val="2">★</span>
                                    <span class="star active" data-val="3">★</span>
                                    <span class="star active" data-val="4">★</span>
                                    <span class="star active" data-val="5">★</span>
                                </div>
                                <div class="rating-label" id="ratingLabel">⭐⭐⭐⭐⭐ 5 - Excellent (Exceeded Expectations)</div>
                            </div>
                        </div>

                        <!-- NPS Recommendation -->
                        <div class="form-group">
                            <label>How likely are you to recommend us? (0 to 10)</label>
                            <div class="nps-group" id="npsGroup">
                                <button type="button" class="nps-btn" data-val="0">0</button>
                                <button type="button" class="nps-btn" data-val="1">1</button>
                                <button type="button" class="nps-btn" data-val="2">2</button>
                                <button type="button" class="nps-btn" data-val="3">3</button>
                                <button type="button" class="nps-btn" data-val="4">4</button>
                                <button type="button" class="nps-btn" data-val="5">5</button>
                                <button type="button" class="nps-btn" data-val="6">6</button>
                                <button type="button" class="nps-btn" data-val="7">7</button>
                                <button type="button" class="nps-btn" data-val="8">8</button>
                                <button type="button" class="nps-btn" data-val="9">9</button>
                                <button type="button" class="nps-btn active" data-val="10">10</button>
                            </div>
                            <div class="nps-subtext">
                                <span>Not Likely (0)</span>
                                <span>Extremely Likely (10)</span>
                            </div>
                        </div>

                        <!-- Review Title & Type -->
                        <div class="row-2 form-group">
                            <div>
                                <label>Review Title / Subject <span class="req">*</span></label>
                                <input type="text" name="name" value="{default_title}" required="1"/>
                            </div>
                            <div>
                                <label>Review Type</label>
                                <select name="review_type">
                                    <option value="completion" {'selected' if is_completed else ''}>Project Completion Sign-Off</option>
                                    <option value="milestone" {'selected' if not is_completed else ''}>Milestone Review</option>
                                    <option value="monthly">Periodic Progress Review</option>
                                    <option value="ad_hoc">General Feedback</option>
                                </select>
                            </div>
                        </div>

                        <!-- Reviewer Info -->
                        <div class="row-2 form-group">
                            <div>
                                <label>Your Name <span class="req">*</span></label>
                                <input type="text" name="reviewer_name" value="{client_name}" required="1"/>
                            </div>
                            <div>
                                <label>Your Email Address <span class="req">*</span></label>
                                <input type="email" name="reviewer_email" value="{client_email}" required="1"/>
                            </div>
                        </div>

                        <!-- Feedback Comments -->
                        <div class="form-group">
                            <label>Customer Feedback &amp; Comments <span class="req">*</span></label>
                            <textarea name="feedback" required="1" placeholder="Please share your experience regarding deliverables, communication, quality, and timelines..."></textarea>
                        </div>

                        <!-- What went well -->
                        <div class="form-group">
                            <label>What Went Well (Key Strengths &amp; Praises)</label>
                            <textarea name="strengths" placeholder="Highlights, positive observations, or praised consultants..."></textarea>
                        </div>

                        <!-- Areas for improvement -->
                        <div class="form-group">
                            <label>Areas for Improvement / Suggestions</label>
                            <textarea name="areas_for_improvement" placeholder="Any bottlenecks, delayed items, or suggestions for future engagements..."></textarea>
                        </div>

                        <button type="submit" class="submit-btn">
                            🚀 Submit Customer Review
                        </button>
                    </form>
                </div>

                <div class="footer-text">
                    Protected by secure token &bull; Benac Business Solutions Project Delivery System
                </div>
            </div>

            <script>
                // Interactive 5-Star Selection
                const ratingLabels = {{
                    1: "⭐ 1 - Unsatisfactory (Significant Issues)",
                    2: "⭐⭐ 2 - Needs Improvement (Minor Issues)",
                    3: "⭐⭐⭐ 3 - Satisfactory (Met Requirements)",
                    4: "⭐⭐⭐⭐ 4 - Very Good (Met Expectations Fully)",
                    5: "⭐⭐⭐⭐⭐ 5 - Excellent (Exceeded Expectations)"
                }};
                const stars = document.querySelectorAll('#starGroup .star');
                const ratingInput = document.getElementById('ratingInput');
                const ratingLabel = document.getElementById('ratingLabel');

                stars.forEach(star => {{
                    star.addEventListener('click', () => {{
                        const val = parseInt(star.getAttribute('data-val'));
                        ratingInput.value = val;
                        ratingLabel.textContent = ratingLabels[val] || '';
                        stars.forEach((s, idx) => {{
                            if (idx < val) {{
                                s.classList.add('active');
                            }} else {{
                                s.classList.remove('active');
                            }}
                        }});
                    }});
                }});

                // Interactive NPS Selection
                const npsButtons = document.querySelectorAll('#npsGroup .nps-btn');
                const npsInput = document.getElementById('npsInput');

                npsButtons.forEach(btn => {{
                    btn.addEventListener('click', () => {{
                        npsButtons.forEach(b => b.classList.remove('active'));
                        btn.classList.add('active');
                        npsInput.value = btn.getAttribute('data-val');
                    }});
                }});
            </script>
        </body>
        </html>
        """
        return request.make_response(html, headers=[('Content-Type', 'text/html')])

    @http.route(['/project/review/<int:project_id>/submit'], type='http', auth='public', website=False, methods=['POST'], csrf=False)
    def customer_review_submit(self, project_id, **post):
        """Handle review form submission, create project.manage.review, and log to chatter."""
        token = post.get('token')
        project, err = self._validate_project_token(project_id, token)
        if err or not project:
            return request.make_response(f"<h2>Error: {err}</h2>", headers=[('Content-Type', 'text/html')])

        reviewer_name = post.get('reviewer_name') or project.partner_id.name or 'Client'
        reviewer_email = post.get('reviewer_email') or project.partner_id.email or ''
        rating = post.get('rating', '5')
        name = post.get('name') or f"Customer Review - {reviewer_name}"
        review_type = post.get('review_type', 'milestone')
        nps_score = post.get('nps_score', '')
        feedback = post.get('feedback', '')
        strengths = post.get('strengths', '')
        areas_for_improvement = post.get('areas_for_improvement', '')

        # Create record in project.manage.review
        review = request.env['project.manage.review'].sudo().create({
            'name': name,
            'project_id': project.id,
            'partner_id': project.partner_id.id,
            'client_coordinator_id': project.client_coordinator_id.id if project.client_coordinator_id else False,
            'reviewer_name': reviewer_name,
            'reviewer_email': reviewer_email,
            'rating': str(rating),
            'review_type': review_type,
            'nps_score': str(nps_score) if nps_score else False,
            'feedback': feedback,
            'strengths': strengths,
            'areas_for_improvement': areas_for_improvement,
            'state': 'submitted',
            'review_date': fields.Date.today(),
            'company_id': project.company_id.id,
        })

        # Post incoming review notification to Project Chatter
        star_str = '⭐' * int(rating) if rating.isdigit() else '⭐'
        chatter_msg = Markup(f"""
        <div style="background: #f0fdf4; border-left: 4px solid #10b981; padding: 14px 18px; border-radius: 6px; font-family: sans-serif;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                <span style="font-weight: 700; color: #065f46; font-size: 15px;">
                    🎉 New Customer Review Received!
                </span>
                <span style="font-size: 18px; color: #f59e0b;">{star_str} ({rating}/5)</span>
            </div>
            <div style="font-size: 13px; color: #334155; margin-bottom: 8px;">
                <b>Review Title:</b> {review.name} ({review.reference})<br/>
                <b>Submitted by:</b> {reviewer_name} &lt;{reviewer_email}&gt;<br/>
                <b>NPS Score:</b> {nps_score or 'N/A'} / 10
            </div>
            <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px; padding: 10px 14px; font-size: 13px; color: #1e293b; margin-bottom: 6px;">
                <b>Feedback:</b><br/>{feedback}
            </div>
        """)
        if strengths:
            chatter_msg += Markup(f"""<div style="font-size: 12px; color: #047857; margin-top: 4px;"><b>Strengths:</b> {strengths}</div>""")
        if areas_for_improvement:
            chatter_msg += Markup(f"""<div style="font-size: 12px; color: #b45309; margin-top: 4px;"><b>Areas for Improvement:</b> {areas_for_improvement}</div>""")
        chatter_msg += Markup("</div>")

        project.sudo().message_post(
            body=chatter_msg,
            message_type='notification',
            subtype_xmlid='mail.mt_note'
        )

        company_name = project.company_id.name or 'Benac Business Solutions'
        # Return celebration confirmation screen
        confirmation_html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8"/>
            <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
            <title>Review Received - Thank You!</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    background: #0b0f19;
                    color: #f8fafc;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    min-height: 100vh;
                    margin: 0;
                    padding: 20px;
                    box-sizing: border-box;
                }}
                .card {{
                    background: #111827;
                    border: 1px solid #243042;
                    border-radius: 16px;
                    padding: 40px 32px;
                    max-width: 520px;
                    text-align: center;
                    box-shadow: 0 25px 50px -12px rgba(0,0,0,0.7);
                }}
                .icon {{
                    font-size: 48px;
                    margin-bottom: 16px;
                }}
                h1 {{
                    font-size: 24px;
                    font-weight: 800;
                    color: #10b981;
                    margin-bottom: 8px;
                }}
                p {{
                    font-size: 14px;
                    color: #94a3b8;
                    line-height: 1.6;
                    margin-bottom: 24px;
                }}
                .summary {{
                    background: #162032;
                    border: 1px solid #243042;
                    border-radius: 10px;
                    padding: 16px;
                    text-align: left;
                    font-size: 13px;
                    color: #cbd5e1;
                    margin-bottom: 24px;
                }}
                .summary-row {{
                    display: flex;
                    justify-content: space-between;
                    margin-bottom: 8px;
                }}
                .summary-row:last-child {{
                    margin-bottom: 0;
                }}
                .close-hint {{
                    font-size: 12px;
                    color: #64748b;
                }}
            </style>
        </head>
        <body>
            <div class="card">
                <div class="icon">🎉</div>
                <h1>Thank You, {reviewer_name}!</h1>
                <p>Your feedback regarding <b>{project.name}</b> has been received and shared with our project delivery leadership.</p>
                
                <div class="summary">
                    <div class="summary-row">
                        <span style="color: #94a3b8;">Review Ref:</span>
                        <span style="font-weight: 700; color: #ffffff;">{review.reference}</span>
                    </div>
                    <div class="summary-row">
                        <span style="color: #94a3b8;">Rating:</span>
                        <span style="font-weight: 700; color: #f59e0b;">{star_str} ({rating}/5)</span>
                    </div>
                    <div class="summary-row">
                        <span style="color: #94a3b8;">Project:</span>
                        <span style="font-weight: 600; color: #ffffff;">{project.name}</span>
                    </div>
                </div>

                <div class="close-hint">
                    You can safely close this browser window.<br/>
                    <b>{company_name}</b> appreciates your partnership!
                </div>
            </div>
        </body>
        </html>
        """
        return request.make_response(confirmation_html, headers=[('Content-Type', 'text/html')])
