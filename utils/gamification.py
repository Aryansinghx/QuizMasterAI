import datetime

def calculate_xp(correct_answers, total_questions, difficulty_multiplier=1):
    """
    LOGIC: BASE XP per correct answer multiplied by difficulty.
    """
    base_xp = 10
    earned_xp = (correct_answers * base_xp) * difficulty_multiplier
    return earned_xp

def update_streak(last_played_date, current_streak):
    """
    Logic: IF THEY PLAYED YESTERDAY , INCREMENT. IF TODAY, KEEP SAME. OTHERWISE RESET.
    """
    today = datetime.date.today()
    if last_played_date == today:
        return current_streak
    elif last_played_date == today - datetime.timedelta(days=1):
        return current_streak + 1
    else:
        return 1