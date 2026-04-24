def calculate_student_completion(student):
    def safe_o2o(attr):
        try:
            return bool(getattr(student, attr))
        except Exception:
            return False

    related = [
        student.achievements.exists(),
        safe_o2o('health_info'),
        student.language_info.exists(),
        student.social_links.exists(),
        student.reprimands.exists(),
        safe_o2o('family_social_status'),
        student.family_members.exists(),
        student.interests.exists(),
        student.social_registries.exists(),
        safe_o2o('dormitory'),
        student.gifteds.exists(),
        student.protection_orders.exists(),
    ]
    total  = len(related)
    filled = sum(1 for x in related if x)
    return round((filled / total) * 100) if total > 0 else 0