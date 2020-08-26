echo "Dumping data to fixture files"
echo "============================="
echo "Workflow templates"
./manage.py dumpdata workflow.workflowtemplate --indent 4 > workflow/fixtures/workflow_templates.json
echo "Workflow nodes"
./manage.py dumpdata workflow.node --indent 4 > workflow/fixtures/nodes.json
echo "Workflow response_types"
./manage.py dumpdata workflow.responsetype --indent 4 > workflow/fixtures/response_types.json
echo "Case stages"
./manage.py dumpdata cases.casestage --indent 4 > cases/fixtures/case_stages.json
echo "Case types"
./manage.py dumpdata cases.casetype --indent 4 > cases/fixtures/case_types.json
echo "Company sectors"
./manage.py dumpdata cases.sector --indent 4 > cases/fixtures/sectors.json
echo "Submission statuses"
./manage.py dumpdata cases.submissionstatus --indent 4 > cases/fixtures/submission_status.json
echo "Submission types"
./manage.py dumpdata cases.submissiontype --indent 4 > cases/fixtures/submission_types.json
echo "Archive reasons"
./manage.py dumpdata cases.archivereason --indent 4 > cases/fixtures/archive_reasons.json


