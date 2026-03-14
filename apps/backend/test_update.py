import asyncio
from app.database import db
import json

async def test():
    # Setup test data
    user = db.create_user(name="Update Test", email="update@test.local")
    uid = user["user_id"]
    
    res = await db.create_resume_atomic_master(
        content="dummy",
        filename="dummy.pdf",
        user_id=uid,
        processing_status="processing"
    )
    rid = res["resume_id"]
    
    print("Testing update_resume with parsed JSON payload...")
    
    updates = {
        'processing_status': 'ready',
        'ats_score': 82,
        'ats_breakdown': {'keywordMatch': 32, 'structuralCompleteness': 20, 'quantifiableImpact': 20, 'formatting': 10},
        'processed_data': {
            'personalInfo': {'name': 'Soumyajit Ghosh'},
            'workExperience': [{'id': 1, 'title': 'Test'}]
        }
    }
    
    try:
        updated = db.update_resume(rid, updates)
        print("Success!", updated["processing_status"])
    except Exception as e:
        print("Attribute Error?!", repr(e))
        import traceback
        traceback.print_exc()

asyncio.run(test())
