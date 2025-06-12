import frappe
from frappe.utils import today, add_days, getdate

@frappe.whitelist()
def check_cloud_expirations():
    notification_date = getdate(today())
    clients = frappe.get_all(
        "Cloud Client",
        filters={
            "status": "Active",
            "expiry_date": add_days(notification_date, 30),
            "notification_sent": 0
        },
        fields=["name"]
    )
    
    for client in clients:
        doc = frappe.get_doc("Cloud Client", client.name)
        doc.schedule_renewal_notification()
        doc.notification_sent = 1
        doc.save()
        
    if clients:
        frappe.log_error(f"Sent {len(clients)} cloud renewal notifications", "Cloud Renewal Job")