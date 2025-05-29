import base64
from pathlib import Path
from fastapi import FastAPI
from typing import Dict, Any, AnyStr, List, Optional
from pydantic import BaseModel
from workflow_use.workflow.service import Workflow
from workflow_use.controller.service import WorkflowController
from workflow_use.schema.views import WorkflowInputSchemaDefinition
from browser_use.browser.browser import BrowserConfig, Browser

from langchain_core.language_models.chat_models import BaseChatModel
# Assuming OPENAI_API_KEY is set in the environment
from langchain_openai import ChatOpenAI


class WorkflowStorage:
	def __init__(self) -> None:
		self.workflow_folder = Path("./tmp").resolve()

	def list_workflows(self) -> List[str]:
		return [f.name for f in self.workflow_folder.iterdir() if f.is_file() and not f.name.startswith('temp_recording')]

	def get_workflow(
		self,
		workflow_name: str,
		*,
		controller: WorkflowController | None = None,
		browser: Browser | None = None,
		llm: BaseChatModel | None = None,
	) -> Optional[Workflow]:
		workflow_path = self.workflow_folder / workflow_name
		if not workflow_path.exists():
			return None
		
		workflow = Workflow.load_from_file(
			workflow_path,
			controller=controller,
			browser=browser,
			llm=llm,
		)
		return workflow


class WorkflowInputSchemaResponse(BaseModel):
	error: Optional[str] = None
	input_schema: Optional[List[WorkflowInputSchemaDefinition]] = None

class WorkflowRunResult(BaseModel):
	error: Optional[str] = None
	screenshot: Optional[str] = None

app = FastAPI()
workflow_storage = WorkflowStorage()

# Default LLM instance to None
llm_instance = None
try:
	llm_instance = ChatOpenAI(model='gpt-4o')
	page_extraction_llm = ChatOpenAI(model='gpt-4o-mini')
except Exception as e:
	typer.secho(f'Error initializing LLM: {e}. Would you like to set your OPENAI_API_KEY?', fg=typer.colors.RED)
	set_openai_api_key = input('Set OPENAI_API_KEY? (y/n): ')
	if set_openai_api_key.lower() == 'y':
		os.environ['OPENAI_API_KEY'] = input('Enter your OPENAI_API_KEY: ')
		llm_instance = ChatOpenAI(model='gpt-4o')
		page_extraction_llm = ChatOpenAI(model='gpt-4o-mini')


@app.get("/hello")
async def hello():
	return {"message": "Hello, World!"}

@app.get("/workflows", status_code=200)
async def get_workflows():
	return {"workflows": workflow_storage.list_workflows()}

@app.get("/workflows/{workflow_name}/input_schema", status_code=200)
async def get_workflow_input_schema(workflow_name: str) -> WorkflowInputSchemaResponse:
	workflow = workflow_storage.get_workflow(workflow_name)
	if not workflow:
		return WorkflowInputSchemaResponse(error=f"Workflow '{workflow_name}' not found")
	
	workflow_input_schema = WorkflowInputSchemaResponse(
		error=None,
		input_schema=workflow.inputs_def
	)
	return workflow_input_schema

@app.post("/workflows/{workflow_name}", status_code=200)
async def run_workflow(workflow_name: str, inputs: Dict[AnyStr, Any]) -> WorkflowRunResult:
	# Instantiate Browser and WorkflowController for the Workflow instance
	# Pass llm_instance for potential agent fallbacks or agentic steps
	cfg = BrowserConfig()
	cfg.headless = True
	browser_instance = Browser(cfg)  # Add any necessary config if required
	controller_instance = WorkflowController()  # Add any necessary config if required

	workflow_obj = workflow_storage.get_workflow(workflow_name, controller=controller_instance, browser=browser_instance, llm=llm_instance)
	if not workflow_obj:
		return WorkflowRunResult(error=f"Workflow '{workflow_name}' not found", result=None)

	try:
		result = await workflow_obj.run(inputs=inputs, close_browser_at_end=True, screenshot=True)
	except Exception as e:
		return WorkflowRunResult(error=str(e), result=None)

	# if result.final_screenshot:
	# 	with open("bl.png", "wb") as f:
	# 		f.write(result.final_screenshot)

	workflow_result = WorkflowRunResult()
	workflow_result.error = None
	if result.final_screenshot:
		workflow_result.screenshot = base64.b64encode(result.final_screenshot).decode('utf-8')
	return workflow_result
