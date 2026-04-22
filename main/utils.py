
def calculate_student_completion(student):
    related = [
        student.achievements.exists(),
        student.health_info.exists(),
        student.language_info.exists(),
        student.social_links.exists(),
        student.reprimands.exists(),
        student.family_social_status.exists(),
        student.family_members.exists(),
        student.interests.exists(),
        student.social_registries.exists(),
        student.dormitories.exists(),
        student.gifteds.exists(),
        student.protection_orders.exists(),
    ]
    total  = len(related)
    filled = sum(1 for exists in related if exists)
    return round((filled / total) * 100) if total > 0 else 0