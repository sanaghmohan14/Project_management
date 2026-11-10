# -*- coding: utf-8 -*-
from markupsafe import Markup
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ProjectManageReview(models.Model):
    _name = 'project.manage.review'
    _description = 'Project Customer Review'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'review_date desc, id desc'

    name = fields.Char(
        string='Review Title / Subject',
        required=True,
        tracking=True,
        help="Summary of the customer review, e.g. 'Phase 1 Delivery Feedback'"
    )
    reference = fields.Char(
        string='Reference',
        readonly=True,
        copy=False,
        default=lambda self: _('New')
    )
    project_id = fields.Many2one(
        'project.manage',
        string='Project',
        required=True,
        tracking=True,
        ondelete='cascade'
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Client',
        related='project_id.partner_id',
        store=True,
        readonly=False,
        tracking=True
    )
    client_coordinator_id = fields.Many2one(
        'res.partner',
        string='Client Implementation Coordinator',
        related='project_id.client_coordinator_id',
        store=True
    )
    reviewer_name = fields.Char(
        string='Reviewer Name',
        tracking=True,
        help="Name of the client representative who provided this review"
    )
    reviewer_email = fields.Char(
        string='Reviewer Email',
        tracking=True
    )
    reviewer_phone = fields.Char(string='Reviewer Phone')
    review_date = fields.Date(
        string='Review Date',
        default=fields.Date.context_today,
        required=True,
        tracking=True
    )
    review_type = fields.Selection([
        ('milestone', 'Milestone Review'),
        ('monthly', 'Periodic / Monthly Progress Review'),
        ('completion', 'Project Completion & Final Sign-Off Review'),
        ('ad_hoc', 'Ad-hoc Customer Feedback'),
    ], string='Review Type', default='milestone', required=True, tracking=True)

    rating = fields.Selection([
        ('5', '⭐⭐⭐⭐⭐ 5 - Excellent (Exceeded Expectations)'),
        ('4', '⭐⭐⭐⭐ 4 - Very Good (Met Expectations Fully)'),
        ('3', '⭐⭐⭐ 3 - Satisfactory (Met Requirements)'),
        ('2', '⭐⭐ 2 - Needs Improvement (Minor Issues)'),
        ('1', '⭐ 1 - Unsatisfactory (Significant Issues)'),
    ], string='Rating', default='5', required=True, tracking=True)

    rating_value = fields.Integer(
        string='Rating Value (1-5)',
        compute='_compute_rating_value',
        store=True
    )
    nps_score = fields.Selection([
        (str(i), str(i)) for i in range(11)
    ], string='NPS Recommendation (0-10)', help="How likely is the client to recommend Benac Business Solutions? (0-10)")

    feedback = fields.Html(
        string='Customer Feedback & Comments',
        help="Direct feedback received from the customer or notes from client review meeting"
    )
    strengths = fields.Text(
        string='What Went Well (Key Strengths)',
        help="Highlights, positive observations, or praised consultants"
    )
    areas_for_improvement = fields.Text(
        string='Areas for Improvement / Bottlenecks',
        help="Challenges, delayed items, or suggestions from the client"
    )

    # Associated Team & Leadership (for reporting and filtering)
    team_id = fields.Many2one(
        'project.manage.team',
        string='Project Team',
        related='project_id.team_id',
        store=True
    )
    manager_id = fields.Many2one(
        'hr.employee',
        string='Project Manager',
        related='project_id.manager_id',
        store=True
    )
    team_lead_id = fields.Many2one(
        'hr.employee',
        string='Team Lead',
        related='project_id.team_lead_id',
        store=True
    )

    # Project Snapshot at Time of Review
    project_progress = fields.Float(
        string='Project Progress (%)',
        related='project_id.progress',
        store=True
    )
    project_health = fields.Selection(
        related='project_id.health',
        string='Project Health',
        store=True
    )
    project_risk = fields.Selection(
        related='project_id.risk_level',
        string='Project Risk',
        store=True
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('under_review', 'Under Management Review'),
        ('approved', 'Reviewed & Acknowledged'),
    ], string='Status', default='draft', required=True, tracking=True)

    # Internal Action Plan & Follow-up
    internal_response = fields.Html(
        string='Internal Action Plan / Response',
        help="Corrective measures, appreciation notes, or actions planned based on this feedback"
    )
    response_sent = fields.Boolean(
        string='Acknowledgement Sent to Client',
        default=False,
        tracking=True
    )
    response_date = fields.Date(string='Acknowledgement Date')

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )

    @api.depends('rating')
    def _compute_rating_value(self):
        for rec in self:
            rec.rating_value = int(rec.rating) if rec.rating and rec.rating.isdigit() else 5

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', _('New')) == _('New'):
                vals['reference'] = self.env['ir.sequence'].next_by_code('project.manage.review') or f"REV-{self.env['ir.sequence'].next_by_code('base') or '0001'}"
        records = super().create(vals_list)
        for rec in records:
            if not rec.reviewer_name and rec.partner_id:
                rec.reviewer_name = rec.partner_id.name
            if not rec.reviewer_email and rec.partner_id:
                rec.reviewer_email = rec.partner_id.email
            if not rec.reviewer_phone and rec.partner_id:
                rec.reviewer_phone = rec.partner_id.phone
        return records

    def action_submit(self):
        for rec in self:
            rec.state = 'submitted'
            rec.message_post(
                body=_("Customer review <b>%s</b> has been submitted with rating <b>%s</b>.") % (rec.name, rec.rating),
                subtype_xmlid='mail.mt_comment'
            )

    def action_review(self):
        for rec in self:
            rec.state = 'under_review'

    def action_approve(self):
        for rec in self:
            rec.state = 'approved'
            rec.message_post(
                body=_("Customer review <b>%s</b> has been marked as Reviewed & Acknowledged by %s.") % (rec.name, self.env.user.name),
                subtype_xmlid='mail.mt_comment'
            )

    def action_reset_draft(self):
        for rec in self:
            rec.state = 'draft'

    def action_send_acknowledgement(self):
        """Send a thank-you email and acknowledgement to the client."""
        self.ensure_one()
        recipient_partner = self.partner_id
        recipient_email = self.reviewer_email or (recipient_partner and recipient_partner.email)
        if not recipient_email:
            raise UserError(_("No email address found for client %s or reviewer.") % (self.reviewer_name or 'Client'))

        body_html = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1e293b; max-width: 650px; margin: 0 auto; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden; background: #ffffff;">
            <div style="background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%); padding: 24px 30px; color: #ffffff;">
                <h2 style="margin: 0; font-size: 20px; font-weight: 700;">Thank You for Your Valued Feedback!</h2>
                <p style="margin: 6px 0 0; font-size: 14px; opacity: 0.9;">Project: {self.project_id.name}</p>
            </div>
            <div style="padding: 28px 30px;">
                <p style="font-size: 15px; line-height: 1.6; margin-top: 0;">
                    Dear <b>{self.reviewer_name or self.partner_id.name}</b>,
                </p>
                <p style="font-size: 14px; line-height: 1.6; color: #334155;">
                    Thank you for taking the time to share your feedback regarding <b>{self.project_id.name}</b>.
                    Your insights help our delivery team maintain the highest standards of consulting and implementation excellence.
                </p>
                <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px 20px; margin: 20px 0;">
                    <div style="font-size: 13px; color: #64748b; text-transform: uppercase; font-weight: 600; letter-spacing: 0.5px;">Review Summary</div>
                    <div style="font-size: 16px; font-weight: 700; color: #0f172a; margin-top: 4px;">{self.name}</div>
                    <div style="margin-top: 8px; font-size: 14px;"><b>Rating:</b> {dict(self._fields['rating'].selection).get(self.rating, '')}</div>
                    <div style="margin-top: 4px; font-size: 14px;"><b>Review Type:</b> {dict(self._fields['review_type'].selection).get(self.review_type, '')}</div>
                </div>
                """
        if self.internal_response:
            body_html += f"""
                <div style="margin: 20px 0;">
                    <h4 style="margin: 0 0 8px; font-size: 14px; color: #0f172a;">Response from our Project Team:</h4>
                    <div style="background: #f1f5f9; padding: 12px 16px; border-left: 4px solid #3b82f6; border-radius: 4px; font-size: 14px; color: #334155;">
                        {self.internal_response}
                    </div>
                </div>
            """
        body_html += f"""
                <p style="font-size: 14px; line-height: 1.6; color: #334155;">
                    If you have any further questions or require additional support, please feel free to contact Project Manager <b>{self.manager_id.name or 'our team'}</b> directly.
                </p>
                <p style="font-size: 14px; color: #64748b; margin-bottom: 0;">
                    Warm regards,<br/>
                    <b>{self.env.user.company_id.name or 'Benac Business Solutions'}</b>
                </p>
            </div>
        </div>
        """

        mail_values = {
            'subject': _("Thank You for Your Feedback: %s (%s)") % (self.project_id.name, self.name),
            'body_html': Markup(body_html),
            'email_to': recipient_email,
            'author_id': self.env.user.partner_id.id,
            'auto_delete': False,
        }
        mail = self.env['mail.mail'].sudo().create(mail_values)
        try:
            mail.send(raise_exception=False)
        except Exception as e:
            _logger.warning("SMTP server timed out or failed to immediately deliver acknowledgement email: %s. Email is queued in Odoo.", e)

        self.write({
            'response_sent': True,
            'response_date': fields.Date.context_today(self),
        })

        self.message_post(
            body=Markup(_("Acknowledgement email successfully sent to <b>%s</b> (%s).")) % (self.reviewer_name or recipient_partner.name, recipient_email),
            message_type='notification',
            subtype_xmlid='mail.mt_note'
        )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Acknowledgement Sent"),
                'message': _("Thank you acknowledgement email sent to %s (%s).") % (self.reviewer_name or recipient_partner.name, recipient_email),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_view_project(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'project.manage',
            'view_mode': 'form',
            'res_id': self.project_id.id,
            'target': 'current',
        }


# =====================================================================
# CLIENT UPDATE WIZARD: SEND PROJECT PROGRESS / COMPLETION TO CLIENT
# =====================================================================
class ProjectManageClientUpdateWizard(models.TransientModel):
    _name = 'project.manage.client.update.wizard'
    _description = 'Send Project Update to Client Wizard'

    project_id = fields.Many2one('project.manage', string='Project', required=True)
    partner_id = fields.Many2one('res.partner', string='Primary Client', required=True)
    client_coordinator_id = fields.Many2one('res.partner', string='Client Implementation Coordinator')
    recipient_partner_ids = fields.Many2many(
        'res.partner', 'pm_client_update_partner_rel',
        'wizard_id', 'partner_id', string='Recipients', required=True
    )
    cc_manager = fields.Boolean(string='CC Project Manager', default=True)
    cc_team_lead = fields.Boolean(string='CC Team Lead', default=True)

    is_completed = fields.Boolean(
        string='Is Project Completed?',
        compute='_compute_is_completed',
        store=True,
        readonly=False
    )
    subject = fields.Char(string='Email Subject', required=True)
    custom_message = fields.Text(
        string='Personal Note / Message to Client',
        help="Optional personal note that will be placed at the top of the update report."
    )
    include_scope_breakdown = fields.Boolean(string='Include Scopes Breakdown', default=True)
    include_review_invitation = fields.Boolean(string='Include Customer Review Invitation', default=True)
    body_html = fields.Html(string='Email Preview', compute='_compute_body_html', store=True, readonly=False)

    @api.depends('project_id')
    def _compute_is_completed(self):
        for rec in self:
            proj = rec.project_id
            rec.is_completed = bool(proj and (proj.state == 'done' or proj.progress >= 100))

    @api.onchange('project_id')
    def _onchange_project_id(self):
        if self.project_id:
            proj = self.project_id
            self.partner_id = proj.partner_id
            self.client_coordinator_id = proj.client_coordinator_id
            recipients = proj.partner_id
            if proj.client_coordinator_id:
                recipients |= proj.client_coordinator_id
            self.recipient_partner_ids = [(6, 0, recipients.ids)]

            if proj.state == 'done' or proj.progress >= 100:
                self.is_completed = True
                self.subject = f"Project Completion Report: {proj.name} - 100% Successfully Delivered"
                self.custom_message = f"Dear {proj.partner_id.name},\n\nWe are delighted to share that all deliverables and milestones for '{proj.name}' have been completed successfully. Please review the final completion summary and deliverables below."
            else:
                self.is_completed = False
                self.subject = f"Project Status & Progress Update: {proj.name} ({int(proj.progress)}% Completed)"
                self.custom_message = f"Dear {proj.partner_id.name},\n\nPlease find below the latest progress update and schedule status for '{proj.name}'."

    @api.depends('project_id', 'is_completed', 'custom_message', 'include_scope_breakdown', 'include_review_invitation')
    def _compute_body_html(self):
        for rec in self:
            proj = rec.project_id
            if not proj:
                rec.body_html = ''
                continue

            # Calculate stats
            total_tasks = len(proj.scope_ids)
            done_tasks = len(proj.scope_ids.filtered(lambda s: s.state == 'done'))
            in_prog_tasks = len(proj.scope_ids.filtered(lambda s: s.state == 'in_progress'))
            pending_tasks = total_tasks - done_tasks - in_prog_tasks
            progress_pct = int(proj.progress)
            health_color = '#10b981' if proj.health == 'good' else ('#f59e0b' if proj.health == 'fair' else '#ef4444')
            health_label = dict(proj._fields['health'].selection).get(proj.health, 'Good')
            risk_label = dict(proj._fields['risk_level'].selection).get(proj.risk_level, 'Low')

            # Build scope breakdown table
            scope_rows = ""
            if rec.include_scope_breakdown and proj.scope_ids:
                scope_groups = {}
                for s in proj.scope_ids:
                    s_name = s.scope or 'General'
                    if s_name not in scope_groups:
                        scope_groups[s_name] = {'total': 0, 'done': 0}
                    scope_groups[s_name]['total'] += 1
                    if s.state == 'done':
                        scope_groups[s_name]['done'] += 1

                for s_name, data in scope_groups.items():
                    s_pct = int((data['done'] / data['total'] * 100)) if data['total'] > 0 else 0
                    bar_color = '#10b981' if s_pct == 100 else '#3b82f6'
                    scope_rows += f"""
                    <tr>
                        <td style="padding: 8px 12px; border-bottom: 1px solid #e2e8f0; font-size: 13px; font-weight: 500;">{s_name}</td>
                        <td style="padding: 8px 12px; border-bottom: 1px solid #e2e8f0; font-size: 13px; text-align: center;">{data['done']} / {data['total']}</td>
                        <td style="padding: 8px 12px; border-bottom: 1px solid #e2e8f0; font-size: 13px;">
                            <div style="background: #e2e8f0; border-radius: 10px; height: 8px; width: 100%; overflow: hidden;">
                                <div style="background: {bar_color}; height: 8px; width: {s_pct}%;"></div>
                            </div>
                        </td>
                        <td style="padding: 8px 12px; border-bottom: 1px solid #e2e8f0; font-size: 13px; font-weight: 600; text-align: right; color: {bar_color};">{s_pct}%</td>
                    </tr>
                    """

            # Message header and banner
            header_gradient = "linear-gradient(135deg, #059669 0%, #10b981 100%)" if rec.is_completed else "linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%)"
            banner_title = "Project Completion Report" if rec.is_completed else "Project Status & Progress Update"
            banner_subtitle = "All deliverables completed successfully" if rec.is_completed else f"Current progress: {progress_pct}% on track"

            html = f"""
            <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1e293b; max-width: 680px; margin: 0 auto; border: 1px solid #e2e8f0; border-radius: 14px; overflow: hidden; background: #ffffff;">
                <!-- Header -->
                <div style="background: {header_gradient}; padding: 26px 32px; color: #ffffff;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <span style="background: rgba(255,255,255,0.2); font-size: 11px; text-transform: uppercase; font-weight: 700; padding: 4px 10px; border-radius: 20px; letter-spacing: 0.5px;">
                                {banner_title}
                            </span>
                            <h2 style="margin: 8px 0 0; font-size: 22px; font-weight: 800;">{proj.name}</h2>
                            <p style="margin: 4px 0 0; font-size: 14px; opacity: 0.9;">{banner_subtitle}</p>
                        </div>
                    </div>
                </div>

                <div style="padding: 28px 32px;">
            """

            # Personal custom note
            if rec.custom_message:
                formatted_note = rec.custom_message.replace('\n', '<br/>')
                html += f"""
                    <div style="background: #f8fafc; border-left: 4px solid #3b82f6; border-radius: 4px; padding: 14px 18px; margin-bottom: 24px; font-size: 14px; line-height: 1.6; color: #334155;">
                        {formatted_note}
                    </div>
                """

            # Key Highlights Cards
            html += f"""
                    <!-- KPI Cards Grid -->
                    <table style="width: 100%; border-collapse: separate; border-spacing: 8px; margin-bottom: 24px;">
                        <tr>
                            <td style="background: #f1f5f9; padding: 14px; border-radius: 8px; text-align: center; width: 25%;">
                                <div style="font-size: 11px; text-transform: uppercase; color: #64748b; font-weight: 700;">Overall Progress</div>
                                <div style="font-size: 24px; font-weight: 800; color: #2563eb; margin-top: 2px;">{progress_pct}%</div>
                            </td>
                            <td style="background: #f1f5f9; padding: 14px; border-radius: 8px; text-align: center; width: 25%;">
                                <div style="font-size: 11px; text-transform: uppercase; color: #64748b; font-weight: 700;">Project Health</div>
                                <div style="font-size: 18px; font-weight: 700; color: {health_color}; margin-top: 4px;">{health_label}</div>
                            </td>
                            <td style="background: #f1f5f9; padding: 14px; border-radius: 8px; text-align: center; width: 25%;">
                                <div style="font-size: 11px; text-transform: uppercase; color: #64748b; font-weight: 700;">Risk Level</div>
                                <div style="font-size: 18px; font-weight: 700; color: #0f172a; margin-top: 4px;">{risk_label}</div>
                            </td>
                            <td style="background: #f1f5f9; padding: 14px; border-radius: 8px; text-align: center; width: 25%;">
                                <div style="font-size: 11px; text-transform: uppercase; color: #64748b; font-weight: 700;">Completed Tasks</div>
                                <div style="font-size: 20px; font-weight: 800; color: #059669; margin-top: 4px;">{done_tasks} / {total_tasks}</div>
                            </td>
                        </tr>
                    </table>

                    <!-- Project Timeline & Contacts -->
                    <table style="width: 100%; font-size: 13px; border-collapse: collapse; margin-bottom: 24px; background: #fafafa; border: 1px solid #e2e8f0; border-radius: 8px;">
                        <tr>
                            <td style="padding: 10px 14px; color: #64748b; width: 25%; font-weight: 600;">Start Date:</td>
                            <td style="padding: 10px 14px; color: #0f172a; width: 25%;">{proj.date_start.strftime('%d %b %Y') if proj.date_start else 'N/A'}</td>
                            <td style="padding: 10px 14px; color: #64748b; width: 25%; font-weight: 600;">Due Date:</td>
                            <td style="padding: 10px 14px; color: #0f172a; width: 25%;">{proj.date_end.strftime('%d %b %Y') if proj.date_end else 'N/A'}</td>
                        </tr>
                        <tr style="border-top: 1px solid #f1f5f9;">
                            <td style="padding: 10px 14px; color: #64748b; font-weight: 600;">Project Manager:</td>
                            <td style="padding: 10px 14px; color: #0f172a;">{proj.manager_id.name or 'N/A'}</td>
                            <td style="padding: 10px 14px; color: #64748b; font-weight: 600;">Team Lead:</td>
                            <td style="padding: 10px 14px; color: #0f172a;">{proj.team_lead_id.name or 'N/A'}</td>
                        </tr>
                    </table>
            """

            # Scopes breakdown table
            if scope_rows:
                html += f"""
                    <h4 style="margin: 0 0 10px; font-size: 14px; font-weight: 700; color: #0f172a;">Scope &amp; Deliverables Breakdown:</h4>
                    <table style="width: 100%; border-collapse: collapse; margin-bottom: 24px;">
                        <thead>
                            <tr style="background: #f8fafc; border-bottom: 2px solid #cbd5e1;">
                                <th style="padding: 8px 12px; text-align: left; font-size: 12px; color: #64748b; text-transform: uppercase;">Scope Area</th>
                                <th style="padding: 8px 12px; text-align: center; font-size: 12px; color: #64748b; text-transform: uppercase;">Tasks</th>
                                <th style="padding: 8px 12px; text-align: left; font-size: 12px; color: #64748b; text-transform: uppercase; width: 35%;">Progress</th>
                                <th style="padding: 8px 12px; text-align: right; font-size: 12px; color: #64748b; text-transform: uppercase;">%</th>
                            </tr>
                        </thead>
                        <tbody>
                            {scope_rows}
                        </tbody>
                    </table>
                """

            # Customer Review invitation block with direct fill link
            if rec.include_review_invitation:
                review_url = proj._get_review_url()
                review_heading = "Project Completion Sign-off & Review" if rec.is_completed else "How are we doing? Share Your Project Feedback"
                review_subtext = (
                    f"All milestones for '{proj.name}' have been finalized. Please take 1 minute to rate our consulting delivery and complete the customer sign-off review."
                    if rec.is_completed else
                    f"We value your partnership! Please take 1 minute to submit your review on our progress, quality, and deliverables for '{proj.name}'."
                )
                html += f"""
                    <div style="background: linear-gradient(135deg, #eff6ff 0%, #f0fdf4 100%); border: 2px dashed #3b82f6; border-radius: 12px; padding: 22px 20px; text-align: center; margin-top: 24px;">
                        <div style="font-size: 22px; margin-bottom: 6px;">⭐⭐⭐⭐⭐</div>
                        <h4 style="margin: 0 0 6px; font-size: 16px; font-weight: 700; color: #1e3a8a;">
                            {review_heading}
                        </h4>
                        <p style="margin: 0 0 16px; font-size: 13px; color: #475569; line-height: 1.5; max-width: 520px; margin-left: auto; margin-right: auto;">
                            {review_subtext}
                        </p>
                        <a href="{review_url}" target="_blank" style="display: inline-block; background: #2563eb; color: #ffffff; font-weight: 700; font-size: 14px; padding: 12px 28px; border-radius: 8px; text-decoration: none; box-shadow: 0 4px 6px -1px rgba(37, 99, 235, 0.3);">
                            👉 Click Here to Fill Customer Review
                        </a>
                        <div style="margin-top: 10px; font-size: 11px; color: #64748b;">
                            Direct link for {proj.partner_id.name or 'Client'} &bull; No login required
                        </div>
                    </div>
                """

            html += f"""
                    <div style="margin-top: 28px; padding-top: 20px; border-top: 1px solid #e2e8f0; font-size: 12px; color: #94a3b8; text-align: center;">
                        Generated by <b>{proj.company_id.name or 'Benac Business Solutions'}</b> Project Management System.<br/>
                        Questions? Contact {proj.manager_id.name or 'your Project Manager'} at {proj.manager_id.work_email or 'support@benac.com'}.
                    </div>
                </div>
            </div>
            """
            rec.body_html = html

    def action_send_update_email(self):
        """Send the formatted update email to all selected recipients."""
        self.ensure_one()
        proj = self.project_id
        recipients = self.recipient_partner_ids
        if not recipients:
            raise UserError(_("Please select at least one client recipient."))

        valid_emails = [p.email.strip() for p in recipients if p.email and p.email.strip()]
        if not valid_emails:
            raise UserError(_("None of the selected recipients have a valid email address configured."))

        # Add CC if selected
        cc_emails = []
        if self.cc_manager and proj.manager_id and proj.manager_id.work_email:
            cc_emails.append(proj.manager_id.work_email)
        if self.cc_team_lead and proj.team_lead_id and proj.team_lead_id.work_email:
            cc_emails.append(proj.team_lead_id.work_email)

        # Create mail.mail record for real outbound delivery
        mail_vals = {
            'subject': self.subject,
            'body_html': Markup(self.body_html),
            'email_to': ', '.join(valid_emails),
            'email_cc': ', '.join(cc_emails) if cc_emails else False,
            'author_id': self.env.user.partner_id.id,
            'auto_delete': False,
        }
        mail = self.env['mail.mail'].sudo().create(mail_vals)
        smtp_success = True
        try:
            # Send without raising exception so SMTP connection timeout or network glitch won't crash the wizard
            mail.send(raise_exception=False)
        except Exception as e:
            smtp_success = False
            _logger.warning("SMTP server timed out or failed to immediately deliver client update email: %s. The email has been queued in Odoo.", e)

        # Log into project chatter as an internal note (without emailing partners a second time)
        update_type_str = _("Project Completion Report") if self.is_completed else _("Project Progress Update (%d%%)") % int(proj.progress)
        chatter_body = Markup(
            "<p><b>%s</b> sent to client <b>%s</b> (%s).</p>"
            "<p><b>Subject:</b> %s</p>"
            "<details><summary style='cursor: pointer; color: #2563eb; font-weight: 600;'>View Sent Email Report</summary>"
            "<div style='margin-top: 10px; border: 1px solid #e2e8f0; padding: 12px; border-radius: 8px;'>%s</div>"
            "</details>"
        ) % (
            update_type_str,
            ', '.join(recipients.mapped('name')),
            ', '.join(valid_emails),
            self.subject,
            Markup(self.body_html)
        )
        proj.message_post(
            body=chatter_body,
            message_type='notification',
            subtype_xmlid='mail.mt_note'
        )

        proj.write({'last_client_update_date': fields.Datetime.now()})

        notification_msg = (
            _("Update report successfully sent to %s!") % (', '.join(recipients.mapped('name')))
            if smtp_success else
            _("Update report logged to project chatter and queued for email delivery to %s. (Note: Outgoing mail server connection timed out)") % (', '.join(recipients.mapped('name')))
        )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Project Update Sent"),
                'message': notification_msg,
                'type': 'success' if smtp_success else 'warning',
                'sticky': False,
            }
        }
