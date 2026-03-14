import asyncio
import httpx

async def run():
    print("Testing bulk upload via API with CSV...")
    async with httpx.AsyncClient() as client:
        # Create a cohort first
        resp = await client.post("http://localhost:8000/api/v1/admin/cohorts", json={"name": "CSV Test Cohort"})
        print("Cohort response:", resp.status_code, resp.text)
        if resp.status_code != 200:
            return
        cohort_id = resp.json()["cohort_id"]
        
        # Create a dummy CSV that has a resume URL
        csv_content = b"Full Name,Email Address,Roll Number,Upload Your Resume\nTest User,test@test.com,TEST02,https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf\n"
        
        files = {
            "files": ("test.csv", csv_content, "text/csv")
        }
        
        resp = await client.post(
            f"http://localhost:8000/api/v1/admin/cohorts/{cohort_id}/bulk-upload-resumes",
            files=files,
            timeout=30.0
        )
        print("Upload response:", resp.status_code, resp.json())

if __name__ == "__main__":
    asyncio.run(run())
