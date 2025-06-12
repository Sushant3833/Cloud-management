# Copyright (c) 2025, sushant and contributors
# For license information, please see license.txt

# import frappe
import frappe
from frappe.model.document import Document
from frappe.utils import add_months, getdate, today, add_days

class CloudClient(Document):
    def validate(self):
        self.validate_start_date()
        self.calculate_expiry_and_renewal()
        self.setup_email_alerts()
    
    def validate_start_date(self):
        if not self.client_name or not self.start_date:
            return
        latest_expiry = frappe.db.sql("""
            SELECT MAX(expiry_date) as latest_expiry
            FROM `tabCloud Client`
            WHERE client_name = %s AND name != %s AND expiry_date IS NOT NULL
        """, (self.client_name, self.name or ''), as_dict=True)[0].latest_expiry
        if latest_expiry:
            latest_expiry_date = getdate(latest_expiry)
            selected_start_date = getdate(self.start_date)
            if selected_start_date <= latest_expiry_date:
                frappe.throw(f"Start Date must be after {latest_expiry_date.strftime('%d-%m-%Y')}")

    def calculate_expiry_and_renewal(self):
        if not self.start_date or not self.cloud_cost or self.cloud_cost <= 0:
            return
        if self.paid_amount and self.cloud_cost > 0:
            months_covered = self.paid_amount / self.cloud_cost
            whole_months = int(months_covered)
            self.expiry_date = add_months(getdate(self.start_date), whole_months)
            self.renewal_date = self.expiry_date
            today_date = getdate(today())
            self.days_remaining = (self.expiry_date - today_date).days if self.expiry_date > today_date else 0
            self.status = "Expired" if self.days_remaining == 0 else "Active"
        else:
            self.expiry_date = self.start_date
            self.renewal_date = self.start_date
            self.days_remaining = 0
    
    def setup_email_alerts(self):
        if not self.expiry_date:
            frappe.log_error("No expiry date", "Cloud Client Alert")
            return
        notification_date = add_days(self.expiry_date, -30)
        today_date = getdate(today())
        frappe.log_error(f"Check: Today={today_date}, Notify={notification_date}, Days={self.days_remaining}, Sent={self.notification_sent}", "Cloud Client Alert Check")
        if today_date >= notification_date and self.days_remaining > 0 and not self.notification_sent:
            frappe.log_error("Triggering email", "Cloud Client Alert Check")
            self.schedule_renewal_notification()
    
    def schedule_renewal_notification(self):
        frappe.log_error("Starting email process", "Cloud Client Email")
        
        if not self.client_contact:
            frappe.log_error("No client_contact set", "Cloud Client Email Failure")
            frappe.msgprint("Please set a Contact")
            return
        recipient = frappe.db.get_value("Contact", self.client_contact, "email_id")
        if not recipient:
            frappe.log_error(f"No email_id for contact {self.client_contact}", "Cloud Client Email Failure")
            frappe.msgprint(f"No email found for contact {self.client_contact}")
            return
        
        customer_name = frappe.db.get_value("Customer", self.client_name, "customer_name")
        if not customer_name:
            frappe.log_error(f"No customer_name for {self.client_name}", "Cloud Client Email Failure")
            customer_name = self.client_name
        
        if not frappe.db.exists("Email Template", "Cloud Service Renewal"):
            frappe.log_error("Creating email template", "Cloud Client Email")
            self.create_email_template()
        
        template_doc = frappe.get_doc("Email Template", "Cloud Service Renewal")
        frappe.log_error(f"Using template: {template_doc.name}", "Cloud Client Email")
        
        try:
            frappe.log_error(f"Sending email to {recipient}", "Cloud Client Email")
            frappe.sendmail(
                recipients=[recipient],
                subject=f"Renewal Reminder - {customer_name}",
                message=frappe.render_template(template_doc.response, {
                    "client_name": customer_name,
                    "cloud_name": self.cloud_name,
                    "expiry_date": self.expiry_date.strftime("%d-%m-%Y"),
                    "monthly_cost": self.cloud_cost,
                    "days_remaining": self.days_remaining
                }),
                send_priority=1
            )
            frappe.log_error(f"Email queued for {recipient}", "Cloud Client Email Success")
            self.notification_sent = 1
            frappe.db.set_value("Cloud Client", self.name, "notification_sent", 1)
            frappe.db.commit()
            frappe.msgprint(f"Email queued for {recipient}")
        except Exception as e:
            frappe.log_error(f"Email failed: {str(e)}", "Cloud Client Email Error")
            frappe.msgprint(f"Email failed: {str(e)}")
    
    def create_email_template(self):
        template = frappe.new_doc("Email Template")
        template.name = "Cloud Service Renewal"
        template.subject = "Your Cloud Service is Due for Renewal"
        template.response = """
        <p>Dear {{ client_name }},</p>
        <p>Your cloud service <strong>{{ cloud_name }}</strong> is due for renewal in <strong>{{ days_remaining }} days</strong>.</p>
        <p><strong>Details:</strong></p>
        <ul>
            <li>Cloud Service: {{ cloud_name }}</li>
            <li>Monthly Cost: {{ monthly_cost }}</li>
            <li>Expiry Date: {{ expiry_date }}</li>
        </ul>
        <p>Please arrange payment before the expiry date.</p>
        <p>Best regards,<br>Your Cloud Service Provider</p>
        """
        template.save()
        frappe.log_error("Template created", "Cloud Client Email")
