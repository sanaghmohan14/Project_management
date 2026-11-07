import base64
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
    ], string='Priority', default='0')
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
    ], string='Health', default='good', compute='_compute_metrics', store=True, readonly=False, tracking=True)
    risk_level = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ], string='Risk Level', default='low', compute='_compute_metrics', store=True, readonly=False, tracking=True)
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

    @api.depends('scope_ids.state', 'date_start', 'date_end', 'state')
    def _compute_metrics(self):
        today = fields.Date.today()
        for rec in self:
            # 1. Progress from tasks if present, otherwise based on stage
            if rec.scope_ids:
                total_tasks = len(rec.scope_ids)
                done_tasks = len(rec.scope_ids.filtered(lambda s: s.state == 'done'))
                rec.progress = round((done_tasks / total_tasks) * 100, 1)
            elif not rec.progress:
                if rec.state == 'done':
                    rec.progress = 100.0
                elif rec.state == 'in_progress':
                    rec.progress = 50.0
                else:
                    rec.progress = 0.0

            # 2. Planned progress based on elapsed time vs total duration
            if rec.date_start and rec.date_end:
                total_days = (rec.date_end - rec.date_start).days
                elapsed_days = (today - rec.date_start).days
                if elapsed_days <= 0:
                    rec.planned_progress = 0.0
                elif total_days > 0:
                    rec.planned_progress = min(round((elapsed_days / total_days) * 100, 1), 100.0)
                else:
                    rec.planned_progress = 100.0
            else:
                rec.planned_progress = rec.progress

            # 3. Running status derived from stage
            if rec.state == 'done':
                rec.running_status = 'completed'
            elif rec.state == 'cancelled':
                rec.running_status = 'on_hold'
            elif rec.state == 'in_progress':
                rec.running_status = 'running'
            else:
                rec.running_status = 'not_started'

            # 4. Condition: ahead, on_plan, behind, overdue
            if rec.date_end and today > rec.date_end and rec.state != 'done':
                rec.condition = 'overdue'
            elif rec.progress >= rec.planned_progress + 5:
                rec.condition = 'ahead'
            elif rec.progress >= rec.planned_progress - 5:
                rec.condition = 'on_plan'
            else:
                rec.condition = 'behind'

            # 5. Default Health & Risk level
            if not rec.health:
                if rec.condition in ('ahead', 'on_plan'):
                    rec.health = 'good'
                elif rec.condition == 'behind':
                    if (rec.planned_progress - rec.progress) > 20:
                        rec.health = 'poor'
                    else:
                        rec.health = 'fair'
                else:
                    rec.health = 'poor'

            if not rec.risk_level:
                if rec.health == 'poor' or rec.condition == 'overdue':
                    rec.risk_level = 'high'
                elif rec.health == 'fair' or rec.condition == 'behind':
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
        domain = []
        if team_id:
            domain.append(('team_id', '=', int(team_id)))

        projects = self.search(domain)
        all_teams = self.env['project.manage.team'].search([])

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
                if team_id and tm.id != int(team_id):
                    continue

                tm_projects = tm.project_ids
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
            })

        all_consultants = self.env['hr.employee'].sudo().search_count([])

        # ---- User Role Identification for Multi-Group Dashboard & Privileges ----
        user = self.env.user
        is_actual_admin = (
            user.has_group('project_manage.group_project_manage_administrator') or
            user.has_group('base.group_system') or
            user.has_group('base.group_erp_manager') or
            (hasattr(user, '_is_admin') and user._is_admin())
        )
        is_actual_ceo = is_actual_admin or user.has_group('project_manage.group_project_manage_ceo')

        # Allow Administrators / Executives to switch role view (e.g., view as CEO)
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

        Scope = self.env['project.manage.scope']
        # Active pending scopes in database across approval stages
        all_pending_scopes = Scope.search([('approval_state', 'in', ('pending_tl', 'pending_pm', 'pending_vp', 'pending_ceo'))])
        all_pending_count = len(all_pending_scopes)

        # Pending items targeted to current user based on their approval tier:
        if role_code in ('admin', 'ceo'):
            my_pending_scopes = all_pending_scopes
        elif role_code == 'vp':
            my_pending_scopes = all_pending_scopes.filtered(lambda s: s.approval_state in ('pending_tl', 'pending_pm', 'pending_vp'))
        elif role_code == 'manager':
            my_pending_scopes = all_pending_scopes.filtered(lambda s: s.approval_state in ('pending_tl', 'pending_pm') and (not s.project_id.manager_id or s.project_id.manager_id.user_id == user))
        elif role_code == 'team_lead':
            my_pending_scopes = all_pending_scopes.filtered(lambda s: s.approval_state == 'pending_tl' and (s.project_id.team_lead_id.user_id == user or s.project_id.team_id.team_lead_id == user))
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
                'can_approve': True,
            })

        # ---- Consultant & Personal Workspace (My Tasks) ----
        current_emp = self.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
        my_tasks_domain = ['|', ('responsible_id.user_id', '=', user.id), ('responsible_id', '=', current_emp.id if current_emp else 0)]
        my_tasks_records = Scope.search(my_tasks_domain)

        my_tasks_list = []
        for s in my_tasks_records[:20]:
            is_late = bool(s.end_date and today > s.end_date and s.state != 'done')
            my_tasks_list.append({
                'id': s.id,
                'name': s.name,
                'code': s.code or (f"S{s.scope_no:02d}" if s.scope_no else '') or s.item_id or '',
                'scope': s.scope or '',
                'project_id': s.project_id.id if s.project_id else False,
                'project_name': s.project_id.name if s.project_id else '',
                'category': s.category or 'Documentation',
                'state': s.state,
                'state_label': dict(s._fields['state'].selection).get(s.state, ''),
                'approval_state': s.approval_state or 'draft',
                'approval_stage_label': dict(s._fields['approval_state'].selection).get(s.approval_state, 'Draft'),
                'can_submit': s.approval_state not in ('approved', 'pending_tl', 'pending_pm', 'pending_vp', 'pending_ceo') and s.state != 'done',
                'end_date': s.end_date.strftime('%d %b') if s.end_date else 'No due date',
                'is_late': is_late,
                'rejection_reason': s.rejection_reason or '',
            })

        # ---- Consultant Top Performers Leaderboard (Actual Database Calculations) ----
        all_emp_scopes = Scope.sudo().search([('responsible_id', '!=', False)])
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
            all_emps = self.env['hr.employee'].sudo().search([], limit=10)
            for emp in all_emps:
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
                'can_switch_roles': is_actual_admin or is_actual_ceo,
                'active_view_mode': role_code,
            },
            'approvals_summary': {
                'pending_my_approval_count': len(pending_items),
                'all_pending_count': all_pending_count,
                'pending_items': pending_items,
            },
            'consultant_workspace': {
                'my_total_tasks': len(my_tasks_records),
                'my_todo_count': len(my_tasks_records.filtered(lambda s: s.state == 'todo')),
                'my_inprogress_count': len(my_tasks_records.filtered(lambda s: s.state == 'in_progress')),
                'my_waiting_approval_count': len(my_tasks_records.filtered(lambda s: s.approval_state in ('pending_tl', 'pending_pm', 'pending_vp', 'pending_ceo'))),
                'my_done_count': len(my_tasks_records.filtered(lambda s: s.state == 'done')),
                'my_rejected_count': len(my_tasks_records.filtered(lambda s: s.approval_state == 'rejected')),
                'my_tasks': my_tasks_list,
            },
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
        }

    # ---- Dashboard Quick Actions ----
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

        today = fields.Date.context_today(self)
        scopes_data = []
        scopes = self.env['project.manage.scope'].search(
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
                'item_id': s.item_id or f"ITEM-{s.id}",
                'scope_no': s.scope_no or 0,
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
                'approval_authority': s.approval_authority or 'TL',
                'responsible_name': s.responsible_id.name if s.responsible_id else (s.responsible or 'Unassigned'),
                'accountable_name': s.accountable_id.name if s.accountable_id else (s.accountable or 'Unassigned'),
                'start_date_str': s.start_date.strftime('%d %b %Y') if s.start_date else '',
                'end_date_str': s.end_date.strftime('%d %b %Y') if s.end_date else 'No deadline',
                'is_overdue': bool(is_overdue),
                'can_submit': s.state in ('todo', 'in_progress'),
                'can_approve': s.state == 'under_review' or (s.approval_state and s.approval_state.startswith('pending')),
            })

        total_count = len(scopes_data)
        doc_items = [s for s in scopes_data if 'doc' in s['category'].lower()]
        imp_items = [s for s in scopes_data if 'imp' in s['category'].lower()]
        done_items = [s for s in scopes_data if s['status_color'] == 'green']
        prog_items = [s for s in scopes_data if s['status_color'] == 'blue']
        pend_items = [s for s in scopes_data if s['status_color'] == 'yellow']
        over_items = [s for s in scopes_data if s['status_color'] == 'red']

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
            },
            'scopes': scopes_data,
            'unique_scopes': unique_scopes,
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
