import base64
import uuid
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ProjectManageTag(models.Model):
    _name = 'project.manage.tag'
    _description = 'Project Tag'

    name = fields.Char(required=True)
    color = fields.Integer(string='Color Index')

    _name_uniq = models.Constraint(
        'unique(name)',
        'Tag name must be unique!',
    )


class ProjectManage(models.Model):
    _name = 'project.manage'
    _description = 'Project'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'priority desc, id desc'

    name = fields.Char(string='Project Name', required=True, tracking=True)
    partner_id = fields.Many2one('res.partner', string='Client', tracking=True,required=True)
    team_id = fields.Many2one('project.manage.team', string='Project Team', tracking=True)
    date_start = fields.Date(string='Start Date', tracking=True,required=True)
    date_end = fields.Date(string='End Date', tracking=True,required=True)
    manager_id = fields.Many2one('hr.employee', string='Project Manager', tracking=True,required=True)
    team_lead_id = fields.Many2one('hr.employee', string='Team Lead', tracking=True,required=True)
    consultant_ids = fields.Many2many(
        'hr.employee', 'project_manage_consultant_rel',
        'project_id', 'employee_id', string='Consultants',required=True)
    client_coordinator_id = fields.Many2one(
        'res.partner', string='Client Implementation Coordinator', tracking=True,required=True)
    project_coordinator_id = fields.Many2one(
        'hr.employee', string='Project Implementation Coordinator', tracking=True)
    tag_ids = fields.Many2many('project.manage.tag', string='Tags')
    access_token = fields.Char(
        string='Review Access Token',
        copy=False,
        default=lambda self: uuid.uuid4().hex
    )

    def _get_review_url(self):
        self.ensure_one()
        if not self.access_token:
            self.access_token = uuid.uuid4().hex
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url') or 'http://localhost:8069'
        return f"{base_url.rstrip('/')}/project/review/{self.id}?token={self.access_token}"

    @api.onchange('team_id')
    def _onchange_team_id(self):
        if self.team_id:
            if self.team_id.team_lead_id:
                emp = self.env['hr.employee'].sudo().search([('user_id', '=', self.team_id.team_lead_id.id)], limit=1)
                if emp:
                    self.team_lead_id = emp
            if self.team_id.member_ids:
                emps = self.env['hr.employee'].sudo().search([('user_id', 'in', self.team_id.member_ids.ids)])
                if emps:
                    self.consultant_ids = [(6, 0, emps.ids)]
    priority = fields.Selection([
        ('0', 'Normal'),
        ('1', 'Low'),
        ('2', 'High'),
        ('3', 'Very High'),
    ], string='Priority', default='0', tracking=True)
    state = fields.Selection([
        ('todo', 'To Do'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ], string='Stage', default='todo', required=True, tracking=True,
        copy=False, group_expand='_group_expand_states')
    color = fields.Integer()
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)

    # ---- Dashboard & Health Metrics ----
    health = fields.Selection([
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
    ], string='Health', compute='_compute_metrics', store=True, readonly=False, tracking=True)
    risk_level = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ], string='Risk Level', compute='_compute_metrics', store=True, readonly=False, tracking=True)
    progress = fields.Float(
        string='Progress (%)', compute='_compute_metrics', store=True, readonly=False, tracking=True)
    planned_progress = fields.Float(
        string='Planned Progress (%)', compute='_compute_metrics', store=True, readonly=False)
    condition = fields.Selection([
        ('ahead', 'Ahead'),
        ('on_plan', 'On plan'),
        ('behind', 'Behind'),
        ('overdue', 'Overdue'),
    ], string='Condition', compute='_compute_metrics', store=True)
    running_status = fields.Selection([
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('on_hold', 'On hold'),
        ('not_started', 'Not started'),
    ], string='Running Status', compute='_compute_metrics', store=True)

    @api.depends(
        'date_start', 'date_end', 'state',
        'scope_ids.state', 'scope_ids.approval_state', 'scope_ids.end_date'
    )
    def _compute_metrics(self):
        today = fields.Date.today()
        for rec in self:
            # Silently auto-fill any scopes missing approval authority
            missing_auth_scopes = rec.scope_ids.filtered(lambda s: not s.approval_authority)
            if missing_auth_scopes:
                missing_auth_scopes.action_populate_approval_authority()

            # 1. Scope & Task Completion Metrics
            total_tasks = len(rec.scope_ids)
            done_tasks = len(rec.scope_ids.filtered(lambda s: s.state == 'done'))
            review_tasks = len(rec.scope_ids.filtered(
                lambda s: s.state == 'under_review' or (s.approval_state and s.approval_state.startswith('pending'))
            ))
            in_prog_tasks = len(rec.scope_ids.filtered(lambda s: s.state == 'in_progress'))
            overdue_tasks = len(rec.scope_ids.filtered(
                lambda s: s.end_date and today > s.end_date and s.state != 'done'
            ))
            rejected_tasks = len(rec.scope_ids.filtered(
                lambda s: s.approval_state == 'rejected'
            ))

            # 2. Project Progress (%) derived from Scope/Task Completion & Stage
            if rec.state == 'done':
                rec.progress = 100.0
            elif total_tasks > 0:
                # Weighted completion: Done (100%), In Review/Pending (75%), In Progress (40%)
                effective_score = (done_tasks * 1.0) + (review_tasks * 0.75) + (in_prog_tasks * 0.40)
                rec.progress = min(max(round((effective_score / total_tasks) * 100, 1), 0.0), 100.0)
            else:
                if rec.state == 'in_progress':
                    if not rec.progress or rec.progress == 0.0:
                        rec.progress = 50.0
                elif rec.state == 'cancelled':
                    pass
                else:
                    rec.progress = 0.0

            # 3. Planned Progress (%) based on Closing Date (date_end) & Timeline Duration
            days_remaining = None
            if rec.date_start and rec.date_end:
                total_days = (rec.date_end - rec.date_start).days
                elapsed_days = (today - rec.date_start).days
                days_remaining = (rec.date_end - today).days

                if elapsed_days <= 0:
                    rec.planned_progress = 0.0
                elif total_days > 0:
                    rec.planned_progress = min(max(round((elapsed_days / total_days) * 100, 1), 0.0), 100.0)
                else:
                    rec.planned_progress = 100.0
            else:
                rec.planned_progress = rec.progress

            # 4. Running Status derived from Project Stage
            if rec.state == 'done':
                rec.running_status = 'completed'
            elif rec.state == 'cancelled':
                rec.running_status = 'on_hold'
            elif rec.state == 'in_progress':
                rec.running_status = 'running'
            else:
                rec.running_status = 'not_started'

            # 5. Project Condition: Ahead, On plan, Behind, Overdue
            # Evaluates Closing Date vs Today, Actual Progress vs Planned Progress, and Task Bottlenecks
            variance = rec.progress - rec.planned_progress
            is_past_closing_date = bool(rec.date_end and today > rec.date_end and rec.state != 'done')

            if rec.state == 'done':
                rec.condition = 'ahead' if (rec.date_end and today < rec.date_end) else 'on_plan'
            elif is_past_closing_date:
                rec.condition = 'overdue'
            elif variance >= 5.0 and overdue_tasks == 0:
                rec.condition = 'ahead'
            elif variance >= -5.0 and overdue_tasks == 0:
                rec.condition = 'on_plan'
            else:
                rec.condition = 'behind'

            # 6. Project Health: Good, Fair, Poor
            # Evaluated dynamically from Timeline, Closing Date, Stage, and Scope/Task Quality
            if rec.state == 'done':
                rec.health = 'good'
            elif rec.condition == 'overdue':
                days_late = (today - rec.date_end).days if rec.date_end else 0
                if days_late > 7 or rec.progress < 70.0 or rejected_tasks > 0:
                    rec.health = 'poor'
                else:
                    rec.health = 'fair'
            elif rec.condition == 'behind':
                lag = rec.planned_progress - rec.progress
                if lag > 20.0 or rejected_tasks >= 2 or overdue_tasks >= 3 or (days_remaining is not None and days_remaining <= 7 and rec.progress < 50.0):
                    rec.health = 'poor'
                else:
                    rec.health = 'fair'
            elif rec.condition == 'on_plan':
                if rejected_tasks >= 2 or overdue_tasks >= 2:
                    rec.health = 'fair'
                else:
                    rec.health = 'good'
            else:
                # Ahead of schedule
                if rejected_tasks >= 2:
                    rec.health = 'fair'
                else:
                    rec.health = 'good'

            # 7. Project Risk Level: Low, Medium, High
            # Evaluated dynamically from Deadline Proximity, Lag Variance, and Task Issues
            if rec.state == 'done':
                rec.risk_level = 'low'
            elif (
                (rec.condition == 'overdue' and rec.progress < 80.0) or
                (rec.date_end and today > rec.date_end and (today - rec.date_end).days > 7) or
                (days_remaining is not None and 0 <= days_remaining <= 7 and rec.progress < 60.0) or
                (rec.planned_progress - rec.progress > 20.0) or
                rejected_tasks >= 3 or
                overdue_tasks >= 3 or
                rec.health == 'poor'
            ):
                rec.risk_level = 'high'
            elif (
                rec.condition in ('behind', 'overdue') or
                (days_remaining is not None and 0 <= days_remaining <= 14 and rec.progress < rec.planned_progress) or
                rejected_tasks in (1, 2) or
                overdue_tasks in (1, 2) or
                rec.health == 'fair'
            ):
                rec.risk_level = 'medium'
            else:
                rec.risk_level = 'low'

    # ---- Scopes & Tasks Relationships ----
    scope_ids = fields.One2many(
        'project.manage.scope', 'project_id', string='Scopes')
    doc_scope_ids = fields.One2many(
        'project.manage.scope', 'project_id',
        domain=[('category', '=', 'Documentation')],
        string='Documentation Tasks')
    imp_scope_ids = fields.One2many(
        'project.manage.scope', 'project_id',
        domain=[('category', '=', 'Implementation')],
        string='Implementation Tasks')

    scope_count = fields.Integer(
        string='Scopes Count', compute='_compute_counts')
    doc_count = fields.Integer(
        string='Documentation Tasks Count', compute='_compute_counts')
    imp_count = fields.Integer(
        string='Implementation Tasks Count', compute='_compute_counts')

    review_ids = fields.One2many(
        'project.manage.review', 'project_id', string='Customer Reviews')
    review_count = fields.Integer(
        string='Review Count', compute='_compute_reviews', store=True)
    average_rating = fields.Float(
        string='Average Rating', compute='_compute_reviews', store=True)
    last_client_update_date = fields.Datetime(
        string='Last Client Update Sent', readonly=True)

    @api.depends('review_ids.rating_value', 'review_ids.state')
    def _compute_reviews(self):
        for rec in self:
            rec.review_count = len(rec.review_ids)
            if rec.review_ids:
                total_val = sum(r.rating_value for r in rec.review_ids)
                rec.average_rating = round(total_val / len(rec.review_ids), 1)
            else:
                rec.average_rating = 0.0

    def _compute_counts(self):
        for rec in self:
            rec.scope_count = len(set(rec.scope_ids.mapped('scope_no'))) if rec.scope_ids else 0
            rec.doc_count = len(rec.scope_ids.filtered(lambda s: s.category == 'Documentation'))
            rec.imp_count = len(rec.scope_ids.filtered(lambda s: s.category == 'Implementation'))

    def action_view_scopes(self):
        self.ensure_one()
        return {
            'name': _('Scopes - %s', self.name),
            'type': 'ir.actions.act_window',
            'res_model': 'project.manage.scope',
            'view_mode': 'kanban,list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    def action_view_docs(self):
        self.ensure_one()
        return {
            'name': _('Documentation Tasks - %s', self.name),
            'type': 'ir.actions.act_window',
            'res_model': 'project.manage.scope',
            'view_mode': 'kanban,list,form',
            'domain': [('project_id', '=', self.id), ('category', '=', 'Documentation')],
            'context': {'default_project_id': self.id, 'default_category': 'Documentation'},
        }

    def action_view_imps(self):
        self.ensure_one()
        return {
            'name': _('Implementation Tasks - %s', self.name),
            'type': 'ir.actions.act_window',
            'res_model': 'project.manage.scope',
            'view_mode': 'kanban,list,form',
            'domain': [('project_id', '=', self.id), ('category', '=', 'Implementation')],
            'context': {'default_project_id': self.id, 'default_category': 'Implementation'},
        }

    def action_view_reviews(self):
        self.ensure_one()
        return {
            'name': _('Customer Reviews - %s', self.name),
            'type': 'ir.actions.act_window',
            'res_model': 'project.manage.review',
            'view_mode': 'list,kanban,form,pivot,graph',
            'domain': [('project_id', '=', self.id)],
            'context': {
                'default_project_id': self.id,
                'default_partner_id': self.partner_id.id,
                'default_reviewer_name': self.partner_id.name,
                'default_reviewer_email': self.partner_id.email,
            },
        }

    def action_create_review(self):
        self.ensure_one()
        return {
            'name': _('New Customer Review - %s', self.name),
            'type': 'ir.actions.act_window',
            'res_model': 'project.manage.review',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_project_id': self.id,
                'default_partner_id': self.partner_id.id,
                'default_reviewer_name': self.partner_id.name,
                'default_reviewer_email': self.partner_id.email,
                'default_review_type': 'completion' if (self.state == 'done' or self.progress >= 100) else 'milestone',
            },
        }

    def action_open_client_update_wizard(self):
        """Open the wizard to send formatted progress/completion report to the client."""
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_("Please assign a client before sending project updates."))
        if not self.partner_id.email and not (self.client_coordinator_id and self.client_coordinator_id.email):
            raise UserError(_("Neither the client '%s' nor coordinator has an email address configured.") % self.partner_id.name)

        recipients = self.partner_id
        if self.client_coordinator_id:
            recipients |= self.client_coordinator_id

        is_completed = bool(self.state == 'done' or self.progress >= 100)
        subject = f"Project Completion Report: {self.name} - 100% Successfully Delivered" if is_completed else f"Project Status & Progress Update: {self.name} ({int(self.progress)}% Completed)"
        custom_note = (
            f"Dear {self.partner_id.name},\n\nWe are pleased to inform you that all deliverables for '{self.name}' have been completed successfully. Please review the final completion summary below."
            if is_completed else
            f"Dear {self.partner_id.name},\n\nPlease find below the latest status, deliverables completion, and progress update for '{self.name}'."
        )

        wizard = self.env['project.manage.client.update.wizard'].create({
            'project_id': self.id,
            'partner_id': self.partner_id.id,
            'client_coordinator_id': self.client_coordinator_id.id if self.client_coordinator_id else False,
            'recipient_partner_ids': [(6, 0, recipients.ids)],
            'is_completed': is_completed,
            'subject': subject,
            'custom_message': custom_note,
        })

        return {
            'name': _('Send Project Update to Client'),
            'type': 'ir.actions.act_window',
            'res_model': 'project.manage.client.update.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_open_import_wizard(self):
        self.ensure_one()
        return {
            'name': _('Import Scopes & Tasks'),
            'type': 'ir.actions.act_window',
            'res_model': 'project.scope.import.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_project_id': self.id},
        }


    def action_remove_duplicate_scopes(self):
        """Find and remove duplicate scope records within this project."""
        self.ensure_one()
        seen = set()
        duplicates = self.env['project.manage.scope']
        # Sort by id ascending to keep the earliest record
        for sc in self.scope_ids.sorted('id'):
            # Define uniqueness key: item_id if present, else (scope, name, category)
            if sc.item_id:
                key = ('item_id', sc.item_id.strip())
            else:
                key = (
                    'tuple',
                    (sc.scope or '').strip().lower(),
                    (sc.name or '').strip().lower(),
                    sc.category or '',
                )
            if key in seen:
                duplicates |= sc
            else:
                seen.add(key)

        removed_count = len(duplicates)
        if duplicates:
            duplicates.unlink()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Duplicate Cleanup'),
                'message': _('Successfully removed %s duplicate scope record(s).', removed_count) if removed_count else _('No duplicate scopes found in this project.'),
                'type': 'success' if removed_count else 'info',
                'sticky': False,
            }
        }

    def action_load_standard_scopes(self):
        self.ensure_one()
        import os
        from odoo import tools
        try:
            csv_path = tools.file_path('project_manage/data/default_scope_data.csv')
        except (FileNotFoundError, AttributeError, ValueError):
            csv_path = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'data', 'default_scope_data.csv'))

        if not csv_path or not os.path.exists(csv_path):
            raise UserError(_('Default scope data template file not found.'))

        with open(csv_path, 'rb') as f:
            data = f.read()

        wizard = self.env['project.scope.import.wizard'].create({
            'project_id': self.id,
            'file': base64.b64encode(data),
            'filename': 'default_scope_data.csv',
            'import_mode': 'append',
        })
        return wizard.action_import()

    @api.model
    def _group_expand_states(self, states, domain=None, *args, **kwargs):
        return [key for key, _val in self._fields['state'].selection]

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_end < rec.date_start:
                raise ValidationError(_('End date cannot be before start date.'))

    # ---- Button actions ----
    def action_start(self):
        for rec in self:
            if rec.state != 'todo':
                raise UserError(_('Only projects in "To Do" can be started.'))
            rec.state = 'in_progress'
            if not rec.date_start:
                rec.date_start = fields.Date.context_today(rec)

    def action_done(self):
        for rec in self:
            if rec.state != 'in_progress':
                raise UserError(_('Only projects "In Progress" can be marked as done.'))
            rec.state = 'done'

    def action_cancel(self):
        for rec in self:
            if rec.state in ('done', 'cancelled'):
                raise UserError(_('This project is already closed.'))
            rec.state = 'cancelled'

    def action_reset_todo(self):
        self.write({'state': 'todo'})

    @api.model
    def get_dashboard_data(self, team_id=None, view_as_role=None, **kwargs):
        today = fields.Date.today()
        user = self.env.user

        # ---- User Role Identification & Privileges ----
        is_actual_admin = (
            user.has_group('project_manage.group_project_manage_administrator') or
            user.has_group('base.group_system') or
            user.has_group('base.group_erp_manager') or
            (hasattr(user, '_is_admin') and user._is_admin())
        )
        is_actual_ceo = is_actual_admin or user.has_group('project_manage.group_project_manage_ceo')
        is_actual_vp = is_actual_ceo or user.has_group('project_manage.group_project_manage_vp')
        is_actual_manager = is_actual_vp or user.has_group('project_manage.group_project_manage_manager')
        is_actual_tl = is_actual_manager or user.has_group('project_manage.group_project_manage_team_lead')

        # Allow Administrators / Executives to preview specific role views
        if (is_actual_admin or is_actual_ceo) and view_as_role:
            target_role = str(view_as_role).strip().lower()
        elif is_actual_admin:
            target_role = 'admin'
        elif is_actual_ceo:
            target_role = 'ceo'
        elif user.has_group('project_manage.group_project_manage_vp'):
            target_role = 'vp'
        elif user.has_group('project_manage.group_project_manage_manager'):
            target_role = 'manager'
        elif user.has_group('project_manage.group_project_manage_team_lead'):
            target_role = 'team_lead'
        else:
            target_role = 'consultant'

        # Only Project Manager, CEO, VP, and Admin can see all teams' data and create projects
        can_see_all_teams = target_role in ('admin', 'ceo', 'vp', 'manager')
        can_create_project = target_role in ('admin', 'ceo', 'vp', 'manager')

        if target_role == 'ceo':
            role_code = 'ceo'
            role_name = 'Chief Executive Officer'
            role_badge = '💼 CEO'
            role_badge_class = 'pm-role-ceo'
        elif target_role == 'admin':
            role_code = 'admin'
            role_name = 'Administrator'
            role_badge = '👑 Administrator'
            role_badge_class = 'pm-role-admin'
        elif target_role == 'vp':
            role_code = 'vp'
            role_name = 'Vice President (VP)'
            role_badge = '⭐ Vice President'
            role_badge_class = 'pm-role-vp'
        elif target_role == 'manager':
            role_code = 'manager'
            role_name = 'Project Manager'
            role_badge = '📋 Project Manager'
            role_badge_class = 'pm-role-manager'
        elif target_role == 'team_lead':
            role_code = 'team_lead'
            role_name = 'Team Lead'
            role_badge = '👥 Team Lead'
            role_badge_class = 'pm-role-lead'
        else:
            role_code = 'consultant'
            role_name = 'Consultant'
            role_badge = '💻 Consultant'
            role_badge_class = 'pm-role-consultant'

        # ---- Dedicated Fast & Safe Handler for Consultant Users ----
        # Consultants strictly view their assigned deliverables in the Tasks Hub.
        # Bypass heavy executive KPI / multi-project calculations to prevent AccessErrors.
        if role_code == 'consultant':
            emp = self.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
            emp_ids = emp.ids if emp else []

            # Consultant sees strictly their assigned tasks (by user_id or linked employee)
            if emp_ids:
                hub_domain = ['|', ('responsible_id.user_id', '=', user.id), ('responsible_id', 'in', emp_ids)]
            else:
                hub_domain = [('responsible_id.user_id', '=', user.id)]

            all_hub_scopes = self.env['project.manage.scope'].sudo().search(hub_domain, order='end_date asc, id desc')

            pending_scopes = all_hub_scopes.filtered(
                lambda s: bool(s.responsible_id) and bool(s.start_date or s.end_date) and s.state not in ('done', 'cancelled')
            )
            completed_scopes = all_hub_scopes.filtered(lambda s: s.state == 'done')
            overdue_scopes = pending_scopes.filtered(lambda s: s.end_date and today > s.end_date)
            waiting_approval_scopes = all_hub_scopes.filtered(
                lambda s: s.approval_state in ('pending_tl', 'pending_pm', 'pending_vp', 'pending_ceo')
            )

            # Collect unique consultants and projects for filtering
            consultants_map = {}
            projects_map = {}
            for s in all_hub_scopes:
                if s.responsible_id:
                    consultants_map[s.responsible_id.id] = s.responsible_id.name
                if s.project_id:
                    projects_map[s.project_id.id] = s.project_id.name

            available_consultants = [{'id': cid, 'name': cname} for cid, cname in sorted(consultants_map.items(), key=lambda x: x[1])]
            available_projects = [{'id': pid, 'name': pname} for pid, pname in sorted(projects_map.items(), key=lambda x: x[1])]

            def _serialize_consultant_task(s):
                is_late = bool(s.end_date and today > s.end_date and s.state != 'done')
                is_pending = bool(s.responsible_id and (s.start_date or s.end_date) and s.state not in ('done', 'cancelled'))
                is_completed = (s.state == 'done')
                is_assigned_to_user = bool(
                    s.responsible_id and (
                        (s.responsible_id.user_id == user) or
                        (emp and s.responsible_id == emp)
                    )
                )
                can_submit = bool(
                    is_assigned_to_user and
                    s.approval_state not in ('approved', 'pending_tl', 'pending_pm', 'pending_vp', 'pending_ceo') and
                    s.state != 'done'
                )
                return {
                    'id': s.id,
                    'name': s.name,
                    'code': s.code or (f"S{s.scope_no:02d}" if s.scope_no else '') or s.item_id or '',
                    'scope': s.scope or '',
                    'project_id': s.project_id.id if s.project_id else False,
                    'project_name': s.project_id.name if s.project_id else 'General Project',
                    'team_name': s.project_id.team_id.name if s.project_id and s.project_id.team_id else '',
                    'category': s.category or 'Documentation',
                    'priority': s.priority or '0',
                    'priority_int': int(s.priority or 0),
                    'responsible_id': s.responsible_id.id if s.responsible_id else False,
                    'responsible_name': s.responsible_id.name if s.responsible_id else (s.responsible or 'Unassigned'),
                    'start_date': s.start_date.strftime('%Y-%m-%d') if s.start_date else '',
                    'start_date_str': s.start_date.strftime('%d %b %Y') if s.start_date else '-',
                    'end_date': s.end_date.strftime('%Y-%m-%d') if s.end_date else '',
                    'end_date_str': s.end_date.strftime('%d %b %Y') if s.end_date else 'No deadline',
                    'is_late': is_late,
                    'is_overdue': is_late,
                    'is_pending': is_pending,
                    'is_completed': is_completed,
                    'state': s.state or 'todo',
                    'state_label': dict(s._fields['state'].selection).get(s.state, 'To Do'),
                    'approval_state': s.approval_state or 'draft',
                    'approval_stage_label': dict(s._fields['approval_state'].selection).get(s.approval_state, 'Draft'),
                    'can_submit': can_submit,
                    'can_approve': False,
                    'rejection_reason': s.rejection_reason or '',
                }

            def _task_sort_key(s):
                is_late = bool(s.end_date and today > s.end_date and s.state != 'done')
                is_pend = bool(s.responsible_id and (s.start_date or s.end_date) and s.state not in ('done', 'cancelled'))
                if is_pend and is_late:
                    return (0, s.end_date or fields.Date.today())
                if is_pend:
                    return (1, s.end_date or fields.Date.from_string('2099-12-31'))
                if s.approval_state in ('pending_tl', 'pending_pm', 'pending_vp', 'pending_ceo'):
                    return (2, s.end_date or fields.Date.from_string('2099-12-31'))
                if s.state == 'done':
                    return (3, s.end_date or fields.Date.from_string('2000-01-01'))
                return (4, s.end_date or fields.Date.from_string('2099-12-31'))

            sorted_scopes = sorted(all_hub_scopes, key=_task_sort_key)
            tasks_list = [_serialize_consultant_task(s) for s in sorted_scopes[:200]]

            tasks_hub_data = {
                'role_code': 'consultant',
                'title': "My Tasks Workspace",
                'subtitle': "Track your assigned pending tasks with issued dates and completed deliverables",
                'role_label': "My Tasks",
                'total_count': len(all_hub_scopes),
                'pending_count': len(pending_scopes),
                'completed_count': len(completed_scopes),
                'overdue_count': len(overdue_scopes),
                'waiting_approval_count': len(waiting_approval_scopes),
                'available_consultants': available_consultants,
                'available_projects': available_projects,
                'tasks': tasks_list,
            }

            user_team_name = (
                all_hub_scopes[0].project_id.team_id.name
                if (all_hub_scopes and all_hub_scopes[0].project_id and all_hub_scopes[0].project_id.team_id)
                else (f"Team {emp.name}" if emp else f"Team {user.name}")
            )

            return {
                'company_name': self.env.company.name,
                'current_date_str': today.strftime('%d %B %Y'),
                'user_info': {
                    'id': user.id,
                    'name': user.name,
                    'role_code': 'consultant',
                    'role_name': 'Consultant',
                    'role_badge': '💻 Consultant',
                    'role_badge_class': 'pm-role-consultant',
                    'is_admin': is_actual_admin,
                    'is_ceo': False,
                    'is_vp': False,
                    'is_manager': False,
                    'is_team_lead': False,
                    'is_consultant': True,
                    'is_executive': False,
                    'can_approve': False,
                    'can_create_project': False,
                    'can_see_all_teams': False,
                    'can_switch_roles': is_actual_admin or is_actual_ceo,
                    'active_view_mode': 'consultant',
                },
                'user_team_name': user_team_name,
                'approvals_summary': {
                    'pending_my_approval_count': 0,
                    'all_pending_count': 0,
                    'pending_items': [],
                },
                'consultant_workspace': {
                    'my_total_tasks': len(pending_scopes),
                    'my_todo_count': len(all_hub_scopes.filtered(lambda s: s.state == 'todo')),
                    'my_inprogress_count': len(all_hub_scopes.filtered(lambda s: s.state == 'in_progress')),
                    'my_waiting_approval_count': len(waiting_approval_scopes),
                    'my_done_count': len(completed_scopes),
                    'my_rejected_count': len(all_hub_scopes.filtered(lambda s: s.approval_state == 'rejected')),
                    'my_tasks': tasks_list,
                },
                'tasks_hub': tasks_hub_data,
                'top_performers': [],
                'total_projects': 0,
                'total_teams': 0,
                'total_consultants': 1,
                'running_count': 0,
                'completed_count': 0,
                'on_hold_count': 0,
                'not_started_count': 0,
                'health_good_count': 0,
                'health_fair_count': 0,
                'health_poor_count': 0,
                'overall_health_score': 100,
                'overall_health_label': 'Good',
                'risk_low_count': 0,
                'risk_med_count': 0,
                'risk_high_count': 0,
                'risk_status_label': 'Low risk',
                'on_time_pct': 100,
                'avg_progress': 0,
                'condition_ahead_count': 0,
                'condition_on_plan_count': 0,
                'condition_behind_count': 0,
                'condition_overdue_count': 0,
                'cond_max_count': 1,
                'donut_good_dash': "238.8 238.8",
                'donut_good_offset': "0",
                'donut_fair_dash': "0 238.8",
                'donut_fair_offset': "0",
                'donut_poor_dash': "0 238.8",
                'donut_poor_offset': "0",
                'risk_needle_angle': -50,
                'teams': [],
                'all_teams_filter': [],
                'projects': [],
                'calendar_events': [],
            }

        emp = self.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)

        # Team Scope: Executives & Managers see all teams; Team Leads see only their team
        if can_see_all_teams:
            all_teams = self.env['project.manage.team'].search([])
            user_teams = all_teams
        else:
            user_teams = self.env['project.manage.team'].search([
                '|',
                ('team_lead_id', '=', user.id),
                ('member_ids', 'in', [user.id])
            ])
            if not user_teams and emp:
                assigned_projects = self.search([
                    '|',
                    ('team_lead_id', '=', emp.id),
                    ('consultant_ids', 'in', [emp.id])
                ])
                user_teams = assigned_projects.mapped('team_id')
            all_teams = user_teams

        if user_teams:
            user_team_name = user_teams[0].name
        elif emp:
            user_team_name = f"Team {emp.name}"
        else:
            user_team_name = f"Team {user.name}"

        # Project Search Domain
        domain = []
        if can_see_all_teams:
            if team_id:
                domain.append(('team_id', '=', int(team_id)))
        else:
            if all_teams:
                if team_id and int(team_id) in all_teams.ids:
                    domain.append(('team_id', '=', int(team_id)))
                else:
                    domain.append(('team_id', 'in', all_teams.ids))
            elif emp:
                domain.append(('team_lead_id', '=', emp.id))
            else:
                domain.append(('team_lead_id.user_id', '=', user.id))

        projects = self.search(domain)

        total_projects = len(projects)
        running_projects = projects.filtered(lambda p: p.running_status == 'running')
        completed_projects = projects.filtered(lambda p: p.running_status == 'completed')
        on_hold_projects = projects.filtered(lambda p: p.running_status == 'on_hold')
        not_started_projects = projects.filtered(lambda p: p.running_status == 'not_started')

        health_good = projects.filtered(lambda p: p.health == 'good')
        health_fair = projects.filtered(lambda p: p.health == 'fair')
        health_poor = projects.filtered(lambda p: p.health == 'poor')

        overall_health_score = round(
            ((len(health_good) * 100) + (len(health_fair) * 60) + (len(health_poor) * 20)) / total_projects
        ) if total_projects else 100

        risk_low = projects.filtered(lambda p: p.risk_level == 'low')
        risk_med = projects.filtered(lambda p: p.risk_level == 'medium')
        risk_high = projects.filtered(lambda p: p.risk_level == 'high')

        cond_ahead = projects.filtered(lambda p: p.condition == 'ahead')
        cond_on_plan = projects.filtered(lambda p: p.condition == 'on_plan')
        cond_behind = projects.filtered(lambda p: p.condition == 'behind')
        cond_overdue = projects.filtered(lambda p: p.condition == 'overdue')

        on_time_count = len(cond_ahead) + len(cond_on_plan)
        on_time_pct = round((on_time_count / total_projects) * 100) if total_projects else 100
        avg_progress = round(sum(projects.mapped('progress')) / total_projects) if total_projects else 0

        # Donut Chart SVG stroke metrics (Circumference C = 2 * PI * 38 = ~238.8)
        circ = 238.8
        good_c = len(health_good)
        fair_c = len(health_fair)
        poor_c = len(health_poor)
        if total_projects:
            good_arc = round((good_c / total_projects) * circ, 1)
            fair_arc = round((fair_c / total_projects) * circ, 1)
            poor_arc = round((poor_c / total_projects) * circ, 1)
        else:
            good_arc = circ
            fair_arc = 0.0
            poor_arc = 0.0

        donut_good_dash = f"{good_arc} {circ}"
        donut_good_offset = "0"
        donut_fair_dash = f"{fair_arc} {circ}"
        donut_fair_offset = f"-{good_arc}"
        donut_poor_dash = f"{poor_arc} {circ}"
        donut_poor_offset = f"-{round(good_arc + fair_arc, 1)}"

        # Speedometer Needle angle (-50deg to +50deg)
        if len(risk_high) >= 2:
            risk_needle_angle = 50
        elif len(risk_high) == 1:
            risk_needle_angle = 30
        elif len(risk_med) > 0:
            risk_needle_angle = 0
        else:
            risk_needle_angle = -50

        cond_max_count = max(len(cond_ahead), len(cond_on_plan), len(cond_behind), len(cond_overdue), 1)

        # Build real teams data from database
        teams_data = []
        filter_teams = []

        if all_teams:
            for tm in all_teams:
                filter_teams.append({
                    'id': tm.id,
                    'name': tm.name,
                    'lead_name': tm.team_lead_id.name if tm.team_lead_id else '',
                })
                if can_see_all_teams and team_id and tm.id != int(team_id):
                    continue

                tm_projects = tm.project_ids
                if not can_see_all_teams:
                    tm_projects = tm_projects.filtered(lambda p: p in projects)
                tm_tot = len(tm_projects)
                tm_healthy = len(tm_projects.filtered(lambda p: p.health == 'good'))
                tm_progress = round(sum(tm_projects.mapped('progress')) / tm_tot) if tm_tot else 0
                tm_on_time = round((len(tm_projects.filtered(lambda p: p.condition in ('ahead', 'on_plan'))) / tm_tot) * 100) if tm_tot else 0

                # Real Quality Score: percentage of completed/reviewed tasks in this team's projects
                tm_scopes = tm_projects.mapped('scope_ids')
                if tm_scopes:
                    done_scopes = len(tm_scopes.filtered(lambda s: s.state in ('done', 'under_review')))
                    tm_quality = round((done_scopes / len(tm_scopes)) * 100)
                elif tm_tot:
                    tm_quality = tm_progress
                else:
                    tm_quality = 0

                # Real Utilisation: ratio of active projects to team members
                if tm.member_ids:
                    active_p = len(tm_projects.filtered(lambda p: p.running_status == 'running'))
                    tm_util = min(round((active_p / len(tm.member_ids)) * 100), 100)
                elif tm_tot:
                    tm_util = 100
                else:
                    tm_util = 0

                if not tm_tot:
                    rating = 'No Projects'
                    rating_class = 'text-bg-secondary'
                    trend_text = '0 projects'
                    trend_color = 'info'
                elif tm_progress >= 85:
                    rating = 'Excellent'
                    rating_class = 'text-bg-success'
                    var = round(sum((p.progress - p.planned_progress) for p in tm_projects) / tm_tot)
                    trend_text = f"+{var} pts vs plan" if var > 0 else (f"{var} pts vs plan" if var < 0 else "On plan")
                    trend_color = 'success'
                elif tm_progress >= 60:
                    rating = 'Good'
                    rating_class = 'text-bg-primary'
                    var = round(sum((p.progress - p.planned_progress) for p in tm_projects) / tm_tot)
                    trend_text = f"+{var} pts vs plan" if var > 0 else (f"{var} pts vs plan" if var < 0 else "On plan")
                    trend_color = 'info' if var >= 0 else 'warning'
                else:
                    rating = 'Needs support'
                    rating_class = 'text-bg-warning'
                    var = round(sum((p.progress - p.planned_progress) for p in tm_projects) / tm_tot)
                    trend_text = f"{var} pts vs plan"
                    trend_color = 'danger'

                teams_data.append({
                    'id': tm.id,
                    'name': tm.name,
                    'lead_name': tm.team_lead_id.name if tm.team_lead_id else 'Unassigned',
                    'members_count': len(tm.member_ids),
                    'projects_count': tm_tot,
                    'healthy_count': tm_healthy,
                    'productivity': tm_progress,
                    'quality': tm_quality,
                    'on_time': tm_on_time,
                    'utilisation': tm_util,
                    'rating': rating,
                    'rating_class': rating_class,
                    'trend_text': trend_text,
                    'trend_color': trend_color,
                })
        else:
            # If no Project Teams have been created in project.manage.team yet,
            # derive actual teams dynamically from assigned Team Leads on projects
            leads = projects.mapped('team_lead_id')
            for idx, lead in enumerate(leads, 1):
                lead_projects = projects.filtered(lambda p: p.team_lead_id == lead)
                tm_tot = len(lead_projects)
                tm_healthy = len(lead_projects.filtered(lambda p: p.health == 'good'))
                tm_progress = round(sum(lead_projects.mapped('progress')) / tm_tot) if tm_tot else 0
                tm_on_time = round((len(lead_projects.filtered(lambda p: p.condition in ('ahead', 'on_plan'))) / tm_tot) * 100) if tm_tot else 0

                tm_scopes = lead_projects.mapped('scope_ids')
                if tm_scopes:
                    done_scopes = len(tm_scopes.filtered(lambda s: s.state in ('done', 'under_review')))
                    tm_quality = round((done_scopes / len(tm_scopes)) * 100)
                else:
                    tm_quality = tm_progress

                consultants = lead_projects.mapped('consultant_ids')
                tm_util = min(round((len(lead_projects.filtered(lambda p: p.running_status == 'running')) / (len(consultants) or 1)) * 100), 100) if consultants else 100

                var = round(sum((p.progress - p.planned_progress) for p in lead_projects) / tm_tot) if tm_tot else 0
                trend_text = f"+{var} pts vs plan" if var > 0 else (f"{var} pts vs plan" if var < 0 else "On plan")
                rating = 'Excellent' if tm_progress >= 85 else ('Good' if tm_progress >= 60 else 'Needs support')

                teams_data.append({
                    'id': f"lead_{lead.id}",
                    'name': f"Team {lead.name}",
                    'lead_name': lead.name,
                    'members_count': len(consultants),
                    'projects_count': tm_tot,
                    'healthy_count': tm_healthy,
                    'productivity': tm_progress,
                    'quality': tm_quality,
                    'on_time': tm_on_time,
                    'utilisation': tm_util,
                    'rating': rating,
                    'rating_class': 'text-bg-success' if rating == 'Excellent' else ('text-bg-primary' if rating == 'Good' else 'text-bg-warning'),
                    'trend_text': trend_text,
                    'trend_color': 'success' if var >= 0 else 'danger',
                })

        # Build real project rows
        projects_list = []
        for p in projects:
            days_late = (today - p.date_end).days if p.date_end and today > p.date_end and p.state != 'done' else 0
            variance = round(p.progress - p.planned_progress)
            var_str = f"+{variance} pts" if variance > 0 else (f"{variance} pts" if variance < 0 else "on plan")
            late_str = f" · {days_late}d late" if days_late > 0 else ""
            due_date_formatted = p.date_end.strftime('%d %b') if p.date_end else 'No due date'
            projects_list.append({
                'id': p.id,
                'name': p.name,
                'client_name': p.partner_id.name or 'No Client',
                'client_city': p.partner_id.city or (p.partner_id.country_id.name if p.partner_id.country_id else ''),
                'team_id': p.team_id.id if p.team_id else False,
                'team_name': p.team_id.name or (f"Team {p.team_lead_id.name}" if p.team_lead_id else 'No Team'),
                'running_status': p.running_status or 'running',
                'running_status_label': dict(p._fields['running_status'].selection).get(p.running_status, 'Running'),
                'health': p.health or 'good',
                'health_label': dict(p._fields['health'].selection).get(p.health, 'Good'),
                'risk_level': p.risk_level or 'low',
                'risk_level_label': dict(p._fields['risk_level'].selection).get(p.risk_level, 'Low'),
                'progress': int(round(p.progress or 0)),
                'planned_progress': int(round(p.planned_progress or 0)),
                'due_date_str': f"{due_date_formatted}{late_str}",
                'variance_str': var_str,
                'condition': p.condition or 'on_plan',
                'condition_label': dict(p._fields['condition'].selection).get(p.condition, 'On plan'),
                'scope_count': p.scope_count,
                'doc_count': p.doc_count,
                'imp_count': p.imp_count,
                'total_tasks': len(p.scope_ids),
                'done_tasks': len(p.scope_ids.filtered(lambda s: s.state == 'done')),
                'review_count': p.review_count,
                'average_rating': p.average_rating,
            })

        # Consultant count: Executive sees total consultants; Team Lead sees team consultants
        if can_see_all_teams:
            all_consultants = self.env['hr.employee'].sudo().search_count([])
        else:
            team_members = all_teams.mapped('member_ids')
            team_member_emps = self.env['hr.employee'].sudo().search([('user_id', 'in', team_members.ids)])
            proj_consultants = projects.mapped('consultant_ids')
            all_consultants = len(team_member_emps | proj_consultants)

        Scope = self.env['project.manage.scope']
        # Active pending scopes in database across approval stages
        if can_see_all_teams:
            all_pending_scopes = Scope.search([('approval_state', 'in', ('pending_tl', 'pending_pm', 'pending_vp', 'pending_ceo'))])
        else:
            all_pending_scopes = Scope.search([
                ('approval_state', 'in', ('pending_tl', 'pending_pm', 'pending_vp', 'pending_ceo')),
                ('project_id', 'in', projects.ids)
            ])
        all_pending_count = len(all_pending_scopes)

        # Pending items targeted to current user based on their approval tier:
        if role_code in ('admin', 'ceo'):
            my_pending_scopes = all_pending_scopes
        elif role_code == 'vp':
            my_pending_scopes = all_pending_scopes.filtered(lambda s: s.approval_state in ('pending_tl', 'pending_pm', 'pending_vp'))
        elif role_code == 'manager':
            my_pending_scopes = all_pending_scopes.filtered(lambda s: s.approval_state in ('pending_tl', 'pending_pm'))
        elif role_code == 'team_lead':
            my_pending_scopes = all_pending_scopes.filtered(
                lambda s: s.approval_state == 'pending_tl' and (
                    (s.project_id and s.project_id in projects) or
                    (s.project_id.team_lead_id.user_id == user) or
                    (s.project_id.team_id in all_teams)
                )
            )
        else:
            my_pending_scopes = Scope.browse()

        pending_items = []
        for s in my_pending_scopes[:20]:
            pending_items.append({
                'id': s.id,
                'name': s.name,
                'code': s.code or (f"S{s.scope_no:02d}" if s.scope_no else '') or s.item_id or '',
                'scope': s.scope or '',
                'project_id': s.project_id.id if s.project_id else False,
                'project_name': s.project_id.name if s.project_id else 'General Project',
                'responsible_name': s.responsible_id.sudo().name if s.responsible_id else (s.responsible or 'Unassigned'),
                'submitted_by': s.submitted_by_id.sudo().name if s.submitted_by_id else (s.responsible_id.sudo().name if s.responsible_id else 'Team Member'),
                'submitted_date': s.submitted_date.strftime('%d %b %H:%M') if s.submitted_date else '',
                'approval_state': s.approval_state,
                'approval_stage_label': dict(s._fields['approval_state'].selection).get(s.approval_state, ''),
                'can_approve': bool(s.can_user_approve),
            })

        # ---- Universal Role-Based Tasks Hub (Pending & Completed Tasks) ----
        # Requirement:
        # - Pending tasks = assigned to employee + date issued (start_date or end_date) + not completed (state != 'done')
        # - Completed tasks = state == 'done'
        # - Consultant: only their assigned tasks (completed and pending)
        # - Team Lead: all consultants in his team / projects (pending and completed)
        # - Project Manager: all tasks under his projects (pending and completed)
        # - Executive (VP, CEO, Admin): all tasks across portfolio / selected team
        current_emp = self.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)

        emp_ids = current_emp.ids if current_emp else []
        if role_code == 'consultant':
            # Consultant sees only their assigned tasks
            hub_domain = ['|', ('responsible_id.user_id', '=', user.id), ('responsible_id', 'in', emp_ids)] if emp_ids else [('responsible_id.user_id', '=', user.id)]
        elif role_code == 'team_lead':
            # Team Lead sees tasks for all consultants in his team / projects
            tl_projects = self.search([
                '|', '|', '|',
                ('team_lead_id', 'in', emp_ids),
                ('team_lead_id.user_id', '=', user.id),
                ('team_id.team_lead_id', '=', user.id),
                ('team_id', 'in', user_teams.ids if user_teams else [])
            ])
            if not tl_projects and projects:
                tl_projects = projects
            hub_domain = ['|', ('project_id', 'in', tl_projects.ids), '|', ('responsible_id.user_id', '=', user.id), ('responsible_id', 'in', emp_ids)]
        elif role_code == 'manager':
            # Project Manager sees all tasks under his projects
            pm_projects = self.search([
                '|', ('manager_id', 'in', emp_ids),
                ('manager_id.user_id', '=', user.id)
            ])
            if not pm_projects:
                pm_projects = projects
            hub_domain = ['|', ('project_id', 'in', pm_projects.ids), '|', ('responsible_id.user_id', '=', user.id), ('responsible_id', 'in', emp_ids)]
        else:
            # Executive (VP, CEO, Admin)
            if team_id:
                team_projects = self.search([('team_id', '=', int(team_id))])
                hub_domain = [('project_id', 'in', team_projects.ids)]
            else:
                hub_domain = []

        all_hub_scopes = Scope.search(hub_domain, order='end_date asc, id desc')

        # Filter strictly by definition:
        # Pending: assigned to employee AND date issued (start or end date set) AND not completed (state != 'done' and state != 'cancelled')
        pending_scopes = all_hub_scopes.filtered(
            lambda s: bool(s.responsible_id) and bool(s.start_date or s.end_date) and s.state not in ('done', 'cancelled')
        )
        completed_scopes = all_hub_scopes.filtered(lambda s: s.state == 'done')
        overdue_scopes = pending_scopes.filtered(lambda s: s.end_date and today > s.end_date)
        waiting_approval_scopes = all_hub_scopes.filtered(
            lambda s: s.approval_state in ('pending_tl', 'pending_pm', 'pending_vp', 'pending_ceo')
        )

        # Collect unique consultants and projects for filtering
        consultants_map = {}
        projects_map = {}
        for s in all_hub_scopes:
            if s.responsible_id:
                consultants_map[s.responsible_id.id] = s.responsible_id.name
            if s.project_id:
                projects_map[s.project_id.id] = s.project_id.name

        available_consultants = [{'id': cid, 'name': cname} for cid, cname in sorted(consultants_map.items(), key=lambda x: x[1])]
        available_projects = [{'id': pid, 'name': pname} for pid, pname in sorted(projects_map.items(), key=lambda x: x[1])]

        def _serialize_task(s):
            is_late = bool(s.end_date and today > s.end_date and s.state != 'done')
            is_pending = bool(s.responsible_id and (s.start_date or s.end_date) and s.state not in ('done', 'cancelled'))
            is_completed = (s.state == 'done')
            is_assigned_to_user = bool(
                s.responsible_id and (
                    (s.responsible_id.user_id == user) or
                    (current_emp and s.responsible_id == current_emp)
                )
            )
            is_eligible_to_complete = bool(is_assigned_to_user or is_actual_admin)
            can_submit = bool(
                is_eligible_to_complete and
                s.approval_state not in ('approved', 'pending_tl', 'pending_pm', 'pending_vp', 'pending_ceo') and
                s.state != 'done'
            )
            return {
                'id': s.id,
                'name': s.name,
                'code': s.code or (f"S{s.scope_no:02d}" if s.scope_no else '') or s.item_id or '',
                'scope': s.scope or '',
                'project_id': s.project_id.id if s.project_id else False,
                'project_name': s.project_id.name if s.project_id else 'General Project',
                'team_name': s.project_id.team_id.name if s.project_id and s.project_id.team_id else '',
                'category': s.category or 'Documentation',
                'priority': s.priority or '0',
                'priority_int': int(s.priority or 0),
                'responsible_id': s.responsible_id.id if s.responsible_id else False,
                'responsible_name': s.responsible_id.name if s.responsible_id else (s.responsible or 'Unassigned'),
                'start_date': s.start_date.strftime('%Y-%m-%d') if s.start_date else '',
                'start_date_str': s.start_date.strftime('%d %b %Y') if s.start_date else '-',
                'end_date': s.end_date.strftime('%Y-%m-%d') if s.end_date else '',
                'end_date_str': s.end_date.strftime('%d %b %Y') if s.end_date else 'No deadline',
                'is_late': is_late,
                'is_overdue': is_late,
                'is_pending': is_pending,
                'is_completed': is_completed,
                'state': s.state or 'todo',
                'state_label': dict(s._fields['state'].selection).get(s.state, 'To Do'),
                'approval_state': s.approval_state or 'draft',
                'approval_stage_label': dict(s._fields['approval_state'].selection).get(s.approval_state, 'Draft'),
                'can_submit': can_submit,
                'can_approve': bool(s.can_user_approve),
                'rejection_reason': s.rejection_reason or '',
            }

        def _task_sort_key(s):
            is_late = bool(s.end_date and today > s.end_date and s.state != 'done')
            is_pend = bool(s.responsible_id and (s.start_date or s.end_date) and s.state not in ('done', 'cancelled'))
            if is_pend and is_late:
                return (0, s.end_date or fields.Date.today())
            if is_pend:
                return (1, s.end_date or fields.Date.from_string('2099-12-31'))
            if s.approval_state in ('pending_tl', 'pending_pm', 'pending_vp', 'pending_ceo'):
                return (2, s.end_date or fields.Date.from_string('2099-12-31'))
            if s.state == 'done':
                return (3, s.end_date or fields.Date.from_string('2000-01-01'))
            return (4, s.end_date or fields.Date.from_string('2099-12-31'))

        sorted_scopes = sorted(all_hub_scopes, key=_task_sort_key)
        tasks_list = [_serialize_task(s) for s in sorted_scopes[:150]]

        if role_code == 'consultant':
            hub_title = "My Tasks Workspace"
            hub_subtitle = "Track your assigned pending tasks with issued dates and completed deliverables"
            hub_role_label = "My Tasks"
        elif role_code == 'team_lead':
            hub_title = "Team Lead Tasks Hub"
            hub_subtitle = f"All consultant tasks across {len(tl_projects)} team project(s)"
            hub_role_label = "Team Tasks"
        elif role_code == 'manager':
            hub_title = "Project Manager Tasks Hub"
            hub_subtitle = f"All tasks across {len(pm_projects)} project(s) under your management"
            hub_role_label = "Project Tasks"
        else:
            hub_title = "Enterprise Tasks Hub"
            hub_subtitle = "Executive tracking of pending deliverables and completed tasks across all projects"
            hub_role_label = "All Tasks"

        tasks_hub_data = {
            'role_code': role_code,
            'title': hub_title,
            'subtitle': hub_subtitle,
            'role_label': hub_role_label,
            'total_count': len(all_hub_scopes),
            'pending_count': len(pending_scopes),
            'completed_count': len(completed_scopes),
            'overdue_count': len(overdue_scopes),
            'waiting_approval_count': len(waiting_approval_scopes),
            'available_consultants': available_consultants,
            'available_projects': available_projects,
            'tasks': tasks_list,
        }

        # ---- Consultant Top Performers Leaderboard (Actual Database Calculations) ----
        if can_see_all_teams:
            all_emp_scopes = Scope.sudo().search([('responsible_id', '!=', False)])
        else:
            all_emp_scopes = Scope.sudo().search([
                ('responsible_id', '!=', False),
                ('project_id', 'in', projects.ids)
            ])
        emp_stats = {}
        for sc in all_emp_scopes:
            emp = sc.sudo().responsible_id
            if not emp or not emp.id:
                continue
            if emp.id not in emp_stats:
                emp_stats[emp.id] = {
                    'id': emp.id,
                    'name': emp.sudo().name or 'Consultant',
                    'job': emp.sudo().job_title or 'Consultant',
                    'total': 0,
                    'completed': 0,
                    'on_time': 0,
                    'in_review': 0,
                }
            st = emp_stats[emp.id]
            st['total'] += 1
            if sc.state == 'done':
                st['completed'] += 1
                if not sc.end_date or not sc.last_approval_date or sc.last_approval_date.date() <= sc.end_date:
                    st['on_time'] += 1
            elif sc.state == 'under_review':
                st['in_review'] += 1

        top_performers = []
        for emp_id, st in emp_stats.items():
            tot = st['total']
            comp = st['completed']
            comp_rate = round((comp / tot) * 100) if tot else 0
            on_time_rate = round((st['on_time'] / comp) * 100) if comp else 100
            score = round((comp_rate * 0.6) + (on_time_rate * 0.4))
            badge = '🏆 Top Performer' if score >= 85 else ('⭐ High Achiever' if score >= 65 else '🚀 Rising Star')
            badge_class = 'pm-badge-gold' if score >= 85 else ('pm-badge-silver' if score >= 65 else 'pm-badge-bronze')
            top_performers.append({
                'id': emp_id,
                'name': st['name'],
                'role': st['job'],
                'total_tasks': tot,
                'completed_tasks': comp,
                'in_review_tasks': st['in_review'],
                'completion_rate': comp_rate,
                'on_time_rate': on_time_rate,
                'score': score,
                'badge': badge,
                'badge_class': badge_class,
            })

        # Fallback to database employees if scopes are not yet assigned to responsible_id
        if not top_performers:
            if can_see_all_teams:
                fallback_emps = self.env['hr.employee'].sudo().search([], limit=10)
            else:
                fallback_emps = (team_member_emps | proj_consultants)[:10] if not can_see_all_teams else []
            for emp in fallback_emps:
                top_performers.append({
                    'id': emp.id,
                    'name': emp.sudo().name or 'Consultant',
                    'role': emp.sudo().job_title or 'Consultant',
                    'total_tasks': 0,
                    'completed_tasks': 0,
                    'in_review_tasks': 0,
                    'completion_rate': 0,
                    'on_time_rate': 100,
                    'score': 0,
                    'badge': '🚀 Ready to Perform',
                    'badge_class': 'pm-badge-bronze',
                })

        top_performers.sort(key=lambda x: (x['score'], x['completed_tasks']), reverse=True)
        for idx, tp in enumerate(top_performers, 1):
            tp['rank'] = idx

        # ---- Build Rich Calendar Events (Tasks Only) ----
        # NOTE: The calendar is strictly a Task Schedule / Deadline Calendar. Projects are excluded per user requirement.
        calendar_events = []
        for p in projects:
            for s in p.scope_ids:
                task_date = s.end_date
                if task_date:
                    is_task_late = bool(s.end_date and today > s.end_date and s.state != 'done')
                    days_rem_task = (task_date - today).days
                    calendar_events.append({
                        'id': f"task_{s.id}",
                        'record_id': s.id,
                        'project_id': p.id,
                        'project_name': p.name,
                        'team_id': p.team_id.id if p.team_id else False,
                        'team_name': p.team_id.name if p.team_id else '',
                        'model': 'project.manage.scope',
                        'type': 'task',
                        'title': s.name,
                        'code': s.code or (f"S{s.scope_no:02d}" if s.scope_no else '') or s.item_id or '',
                        'category': s.category or 'Documentation',
                        'item_type': s.item_type or '',
                        'responsible_name': s.responsible_id.sudo().name if s.responsible_id else (s.responsible or 'Unassigned'),
                        'start_date': s.start_date.strftime('%Y-%m-%d') if s.start_date else '',
                        'end_date': task_date.strftime('%Y-%m-%d'),
                        'date': task_date.strftime('%Y-%m-%d'),
                        'date_str': task_date.strftime('%d %b %Y'),
                        'status': s.state or 'todo',
                        'status_label': dict(s._fields['state'].selection).get(s.state, 'To Do'),
                        'approval_state': s.approval_state or 'draft',
                        'approval_label': dict(s._fields['approval_state'].selection).get(s.approval_state, 'Draft'),
                        'is_overdue': is_task_late,
                        'days_remaining': days_rem_task,
                    })

        return {
            'company_name': self.env.company.name,
            'current_date_str': today.strftime('%d %B %Y'),
            'user_info': {
                'id': user.id,
                'name': user.name,
                'role_code': role_code,
                'role_name': role_name,
                'role_badge': role_badge,
                'role_badge_class': role_badge_class,
                'is_admin': is_actual_admin,
                'is_ceo': is_actual_ceo or role_code in ('admin', 'ceo'),
                'is_vp': is_actual_admin or is_actual_ceo or role_code in ('admin', 'ceo', 'vp'),
                'is_manager': is_actual_admin or role_code in ('admin', 'ceo', 'vp', 'manager'),
                'is_team_lead': is_actual_admin or role_code in ('admin', 'ceo', 'vp', 'manager', 'team_lead'),
                'is_consultant': role_code == 'consultant' and not is_actual_admin,
                'is_executive': is_actual_admin or is_actual_ceo or role_code in ('admin', 'ceo', 'vp'),
                'can_approve': True if (is_actual_admin or is_actual_ceo) else role_code in ('vp', 'manager', 'team_lead'),
                'can_create_project': can_create_project,
                'can_see_all_teams': can_see_all_teams,
                'can_switch_roles': is_actual_admin or is_actual_ceo,
                'active_view_mode': role_code,
            },
            'user_team_name': user_team_name,
            'approvals_summary': {
                'pending_my_approval_count': len(pending_items),
                'all_pending_count': all_pending_count,
                'pending_items': pending_items,
            },
            'consultant_workspace': {
                'my_total_tasks': len(pending_scopes) if role_code == 'consultant' else len(all_hub_scopes),
                'my_todo_count': len(all_hub_scopes.filtered(lambda s: s.state == 'todo')),
                'my_inprogress_count': len(all_hub_scopes.filtered(lambda s: s.state == 'in_progress')),
                'my_waiting_approval_count': len(waiting_approval_scopes),
                'my_done_count': len(completed_scopes),
                'my_rejected_count': len(all_hub_scopes.filtered(lambda s: s.approval_state == 'rejected')),
                'my_tasks': tasks_list,
            },
            'tasks_hub': tasks_hub_data,
            'top_performers': top_performers,
            'total_projects': total_projects,
            'total_teams': len(teams_data),
            'total_consultants': all_consultants,
            'running_count': len(running_projects),
            'completed_count': len(completed_projects),
            'on_hold_count': len(on_hold_projects),
            'not_started_count': len(not_started_projects),
            'health_good_count': len(health_good),
            'health_fair_count': len(health_fair),
            'health_poor_count': len(health_poor),
            'overall_health_score': overall_health_score,
            'overall_health_label': 'Good' if overall_health_score >= 70 else ('Fair' if overall_health_score >= 50 else 'Poor'),
            'risk_low_count': len(risk_low),
            'risk_med_count': len(risk_med),
            'risk_high_count': len(risk_high),
            'risk_status_label': 'High risk' if len(risk_high) >= 2 else ('Low to medium risk' if len(risk_high) > 0 or len(risk_med) > 0 else 'Low risk'),
            'on_time_pct': on_time_pct,
            'avg_progress': avg_progress,
            'condition_ahead_count': len(cond_ahead),
            'condition_on_plan_count': len(cond_on_plan),
            'condition_behind_count': len(cond_behind),
            'condition_overdue_count': len(cond_overdue),
            'cond_max_count': cond_max_count,
            'donut_good_dash': donut_good_dash,
            'donut_good_offset': donut_good_offset,
            'donut_fair_dash': donut_fair_dash,
            'donut_fair_offset': donut_fair_offset,
            'donut_poor_dash': donut_poor_dash,
            'donut_poor_offset': donut_poor_offset,
            'risk_needle_angle': risk_needle_angle,
            'teams': teams_data,
            'all_teams_filter': filter_teams,
            'projects': projects_list,
            'calendar_events': calendar_events,
        }

    # ---- Dashboard Quick Actions ----
    @api.model
    def action_dashboard_start_scope(self, scope_id):
        scope = self.env['project.manage.scope'].browse(scope_id)
        if scope.exists():
            scope.action_start()
            return True
        return False

    @api.model
    def action_dashboard_approve_scope(self, scope_id, note=None):
        scope = self.env['project.manage.scope'].browse(scope_id)
        if scope.exists():
            scope.action_approve_level(note=note)
            return True
        return False

    @api.model
    def action_dashboard_reject_scope(self, scope_id, reason=None):
        scope = self.env['project.manage.scope'].browse(scope_id)
        if scope.exists():
            scope.action_reject_level(reason=reason)
            return True
        return False

    @api.model
    def action_dashboard_submit_scope(self, scope_id):
        scope = self.env['project.manage.scope'].browse(scope_id)
        if scope.exists():
            scope.action_submit_for_approval()
            return True
        return False

    @api.model
    def get_project_scopes_dashboard(self, project_id):
        """Return all Scopes, Documentation, and Implementation tasks under a project

        with color codes, category filters, and summary stats for dashboard management.
        """
        project = self.browse(project_id)
        if not project.exists():
            return {'project': {}, 'scopes': [], 'unique_scopes': [], 'stats': {}}
        try:
            project.check_access('read')
        except Exception:
            return {'project': {}, 'scopes': [], 'unique_scopes': [], 'stats': {}}

        today = fields.Date.context_today(self)
        user = self.env.user
        current_emp = self.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
        is_admin = (
            user.has_group('project_manage.group_project_manage_administrator') or
            user.has_group('base.group_system') or
            user.id in (1, 2)
        )

        scopes_data = []
        scopes = self.env['project.manage.scope'].sudo().search(
            [('project_id', '=', project.id)],
            order='scope_no asc, category asc, item_no asc, id asc'
        )

        unique_scopes = []
        scope_map = {}

        for s in scopes:
            is_overdue = s.end_date and today > s.end_date and s.state != 'done'

            # Status color mapping:
            # - Green: Completed / Done
            # - Blue: In Progress
            # - Yellow: Pending / Waiting Review / Approval
            # - Red: Overdue / Cancelled / Rejected
            # - Slate: To Do / Draft
            if s.state == 'done':
                status_color = 'green'
                status_label = 'Completed'
            elif s.state == 'in_progress':
                status_color = 'blue'
                status_label = 'In Progress'
            elif s.state in ('under_review', 'pending_tl', 'pending_pm', 'pending_vp', 'pending_ceo') or (s.approval_state and s.approval_state.startswith('pending')):
                status_color = 'yellow'
                status_label = dict(s._fields['approval_state'].selection).get(s.approval_state, 'Under Review')
            elif is_overdue or s.state == 'cancelled':
                status_color = 'red'
                status_label = 'Overdue' if is_overdue else 'Cancelled'
            else:
                status_color = 'slate'
                status_label = 'To Do'

            # Category color mapping:
            # - Documentation: Blue pill
            # - Implementation: Purple pill
            # - Scope: Teal pill
            cat_str = str(s.category or 'Documentation').strip()
            cat_lower = cat_str.lower()
            if 'doc' in cat_lower:
                category_color = 'blue'
                category_label = 'Documentation'
                cat_badge_class = 'pm-cat-doc'
                cat_icon = 'fa-file-text-o'
            elif 'imp' in cat_lower:
                category_color = 'purple'
                category_label = 'Implementation'
                cat_badge_class = 'pm-cat-imp'
                cat_icon = 'fa-cogs'
            else:
                category_color = 'teal'
                category_label = cat_str or 'Scope'
                cat_badge_class = 'pm-cat-scope'
                cat_icon = 'fa-folder-o'

            scope_name = s.scope or f"Scope {s.scope_no or 0}"
            if scope_name not in scope_map:
                scope_map[scope_name] = {
                    'name': scope_name,
                    'scope_no': s.scope_no or 0,
                    'total': 0,
                    'done': 0,
                }
                unique_scopes.append(scope_map[scope_name])
            scope_map[scope_name]['total'] += 1
            if s.state == 'done':
                scope_map[scope_name]['done'] += 1

            scopes_data.append({
                'id': s.id,
                'priority': s.priority or '0',
                'priority_int': int(s.priority or 0),
                'item_id': s.item_id or f"ITEM-{s.id}",
                'scope_no': s.scope_no or 0,
                'scope': s.scope or '',
                'scope_name': scope_name,
                'name': s.name or s.item_id or 'Untitled Task',
                'category': cat_str,
                'category_color': category_color,
                'category_label': category_label,
                'cat_badge_class': cat_badge_class,
                'cat_icon': cat_icon,
                'item_type': s.item_type or '',
                'evidence_proof': s.evidence_proof or '',
                'state': s.state or 'todo',
                'status_color': status_color,
                'status_label': status_label,
                'approval_state': s.approval_state or 'draft',
                'responsible_id': s.responsible_id.id if s.responsible_id else False,
                'responsible_name': s.responsible_id.name if s.responsible_id else (s.responsible or 'Unassigned'),
                'start_date': s.start_date.strftime('%Y-%m-%d') if s.start_date else '',
                'start_date_str': s.start_date.strftime('%d %b %Y') if s.start_date else '',
                'end_date': s.end_date.strftime('%Y-%m-%d') if s.end_date else '',
                'end_date_str': s.end_date.strftime('%d %b %Y') if s.end_date else 'No deadline',
                'is_overdue': bool(is_overdue),
                'rejection_reason': s.rejection_reason or '',
                'can_start': s.state == 'todo' and bool(
                    is_admin or (s.responsible_id and (
                        (s.responsible_id.user_id == user) or (current_emp and s.responsible_id == current_emp)
                    ))
                ),
                'can_submit': s.state in ('todo', 'in_progress') and bool(
                    is_admin or (s.responsible_id and (
                        (s.responsible_id.user_id == user) or (current_emp and s.responsible_id == current_emp)
                    ))
                ) and s.approval_state not in ('approved', 'pending_tl', 'pending_pm', 'pending_vp', 'pending_ceo'),
                'can_approve': bool(s.can_user_approve),
            })

        total_count = len(scopes_data)
        doc_items = [s for s in scopes_data if 'doc' in s['category'].lower()]
        imp_items = [s for s in scopes_data if 'imp' in s['category'].lower()]
        done_items = [s for s in scopes_data if s['status_color'] == 'green']
        prog_items = [s for s in scopes_data if s['status_color'] == 'blue']
        pend_items = [s for s in scopes_data if s['status_color'] == 'yellow']
        over_items = [s for s in scopes_data if s['status_color'] == 'red']

        # Available employees & consultants for dropdown selection
        proj_emps = project.consultant_ids
        if project.team_lead_id:
            proj_emps |= project.team_lead_id
        if project.manager_id:
            proj_emps |= project.manager_id
        if project.team_id and project.team_id.member_ids:
            team_emps = self.env['hr.employee'].sudo().search([('user_id', 'in', project.team_id.member_ids.ids)])
            proj_emps |= team_emps

        all_active_emps = self.env['hr.employee'].sudo().search([('active', '=', True)], order='name asc')
        combo_emps = proj_emps | all_active_emps
        available_employees = [{'id': e.id, 'name': e.name} for e in combo_emps]

        return {
            'project': {
                'id': project.id,
                'name': project.name,
                'client_name': project.partner_id.name or 'No Client',
                'team_name': project.team_id.name or (f"Team {project.team_lead_id.name}" if project.team_lead_id else 'No Team'),
                'progress': int(round(project.progress or 0)),
                'planned_progress': int(round(project.planned_progress or 0)),
                'running_status': project.running_status or 'running',
                'running_status_label': dict(project._fields['running_status'].selection).get(project.running_status, 'Running'),
                'health': project.health or 'good',
                'health_label': dict(project._fields['health'].selection).get(project.health, 'Good'),
                'risk_level': project.risk_level or 'low',
                'risk_level_label': dict(project._fields['risk_level'].selection).get(project.risk_level, 'Low'),
                'due_date_str': project.date_end.strftime('%d %b %Y') if project.date_end else 'No due date',
                'review_count': project.review_count,
                'average_rating': project.average_rating,
            },
            'scopes': scopes_data,
            'unique_scopes': unique_scopes,
            'available_employees': available_employees,
            'available_scopes': list(scope_map.keys()),
            'stats': {
                'total_items': total_count,
                'total_scopes': len(unique_scopes),
                'total_docs': len(doc_items),
                'done_docs': len([d for d in doc_items if d['status_color'] == 'green']),
                'total_imps': len(imp_items),
                'done_imps': len([i for i in imp_items if i['status_color'] == 'green']),
                'completed_count': len(done_items),
                'in_progress_count': len(prog_items),
                'pending_count': len(pend_items),
                'overdue_count': len(over_items),
                'completion_pct': round((len(done_items) / total_count * 100)) if total_count else 0,
            }
        }

    @api.model
    def save_scope_inline(self, scope_id, vals):
        """Update a scope record inline from the dashboard and return refreshed scopes data."""
        scope = self.env['project.manage.scope'].browse(scope_id)
        if not scope.exists():
            return {'error': _("Scope item not found")}

        write_vals = {}
        if 'scope' in vals:
            write_vals['scope'] = vals['scope']
        if 'category' in vals and vals['category'] in ('Documentation', 'Implementation'):
            write_vals['category'] = vals['category']
        if 'name' in vals and vals['name']:
            write_vals['name'] = vals['name']
        if 'item_type' in vals:
            write_vals['item_type'] = vals['item_type']
        if 'priority' in vals and str(vals['priority']) in ('0', '1', '2', '3'):
            write_vals['priority'] = str(vals['priority'])
        if 'responsible_id' in vals:
            raw_emp = vals['responsible_id']
            emp_id = int(raw_emp) if raw_emp and str(raw_emp).isdigit() else False
            write_vals['responsible_id'] = emp_id
            if emp_id:
                emp = self.env['hr.employee'].sudo().browse(emp_id)
                write_vals['responsible'] = emp.name if emp.exists() else ''
            else:
                write_vals['responsible'] = ''
        if 'start_date' in vals:
            write_vals['start_date'] = vals['start_date'] or False
        if 'end_date' in vals:
            write_vals['end_date'] = vals['end_date'] or False
        if 'state' in vals and vals['state'] in ('todo', 'in_progress', 'under_review', 'done', 'cancelled'):
            new_st = vals['state']
            write_vals['state'] = new_st
            if new_st == 'done':
                write_vals['approval_state'] = 'approved'
            elif new_st == 'under_review':
                write_vals['approval_state'] = 'pending_tl'
                write_vals['submitted_by_id'] = self.env.user.id
                write_vals['submitted_date'] = fields.Datetime.now()
            elif new_st == 'in_progress' and scope.approval_state == 'draft':
                write_vals['approval_state'] = 'in_progress'
            elif new_st == 'todo':
                write_vals['approval_state'] = 'draft'

        scope.write(write_vals)
        if scope.project_id:
            scope.project_id._compute_metrics()

        return self.get_project_scopes_dashboard(scope.project_id.id)

    @api.model
    def create_scope_from_dashboard(self, project_id, vals):
        """Create a new scope record directly from the dashboard wizard and return refreshed data."""
        project = self.browse(project_id)
        if not project.exists():
            return {'error': _("Project not found")}

        scope_str = (vals.get('scope') or '').strip()
        scope_no = 0
        if scope_str:
            existing = self.env['project.manage.scope'].search(
                [('project_id', '=', project.id), ('scope', '=ilike', scope_str)], limit=1)
            if existing:
                scope_no = existing.scope_no

        raw_emp = vals.get('responsible_id')
        emp_id = int(raw_emp) if raw_emp and str(raw_emp).isdigit() else False
        emp_name = ''
        if emp_id:
            emp = self.env['hr.employee'].sudo().browse(emp_id)
            emp_name = emp.name if emp.exists() else ''

        state_val = vals.get('state') or 'todo'
        appr_state = 'approved' if state_val == 'done' else ('in_progress' if state_val == 'in_progress' else 'draft')

        create_vals = {
            'project_id': project.id,
            'scope': scope_str or 'General Scope',
            'scope_no': scope_no,
            'category': vals.get('category') or 'Documentation',
            'name': vals.get('name') or 'Untitled Task',
            'item_type': vals.get('item_type') or '',
            'responsible_id': emp_id,
            'responsible': emp_name,
            'start_date': vals.get('start_date') or False,
            'end_date': vals.get('end_date') or False,
            'state': state_val,
            'approval_state': appr_state,
            'priority': str(vals.get('priority') or '0'),
        }
        self.env['project.manage.scope'].create(create_vals)
        project._compute_metrics()
        return self.get_project_scopes_dashboard(project.id)

    @api.model
    def bulk_fill_scopes(self, project_id, scope_ids, vals):
        """Bulk update multiple scopes by IDs or by scope name from the dashboard bulk fill wizard."""
        project = self.browse(project_id)
        if not project.exists():
            return {'error': _("Project not found")}

        domain = [('project_id', '=', project.id)]
        if scope_ids and isinstance(scope_ids, list):
            domain.append(('id', 'in', scope_ids))
        elif vals.get('scope_name_filter'):
            domain.append(('scope', '=', vals['scope_name_filter']))

        scopes = self.env['project.manage.scope'].search(domain)
        write_vals = {}
        if vals.get('responsible_id'):
            raw_emp = vals['responsible_id']
            emp_id = int(raw_emp) if raw_emp and str(raw_emp).isdigit() else False
            emp = self.env['hr.employee'].sudo().browse(emp_id)
            write_vals['responsible_id'] = emp_id
            write_vals['responsible'] = emp.name if emp.exists() else ''
        elif vals.get('clear_responsible'):
            write_vals['responsible_id'] = False
            write_vals['responsible'] = ''

        if vals.get('start_date'):
            write_vals['start_date'] = vals['start_date']

        if vals.get('end_date'):
            write_vals['end_date'] = vals['end_date']

        if vals.get('category') and vals['category'] in ('Documentation', 'Implementation'):
            write_vals['category'] = vals['category']

        if vals.get('priority') and str(vals['priority']) in ('0', '1', '2', '3'):
            write_vals['priority'] = str(vals['priority'])

        if vals.get('state') and vals['state'] in ('todo', 'in_progress', 'under_review', 'done', 'cancelled'):
            new_st = vals['state']
            write_vals['state'] = new_st
            if new_st == 'done':
                write_vals['approval_state'] = 'approved'
            elif new_st == 'under_review':
                write_vals['approval_state'] = 'pending_tl'
                write_vals['submitted_by_id'] = self.env.user.id
                write_vals['submitted_date'] = fields.Datetime.now()
            elif new_st == 'in_progress':
                write_vals['approval_state'] = 'in_progress'
            elif new_st == 'todo':
                write_vals['approval_state'] = 'draft'

        if write_vals:
            scopes.write(write_vals)
            project._compute_metrics()

        return self.get_project_scopes_dashboard(project.id)
