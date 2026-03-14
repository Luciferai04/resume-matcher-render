from app.database import db
def list_stuff():
    cohorts = db.list_cohorts()
    print(f"Cohorts: {len(cohorts)}")
    for c in cohorts:
        print(f" - {c['name']} ({c['cohort_id']})")

if __name__ == "__main__":
    list_stuff()
