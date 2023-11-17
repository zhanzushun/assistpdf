import logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(funcName)s - %(message)s",
    level=logging.INFO
)

import os
from typing import Dict,List
import json
import hashlib
from datetime import datetime
import time
from pathlib import Path
import uuid



from fastapi import FastAPI, UploadFile, File, Request, BackgroundTasks, Body
from fastapi.responses import StreamingResponse
app = FastAPI()

# from fastapi.middleware.cors import CORSMiddleware
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

import config
from fastapi.staticfiles import StaticFiles

STATIC_FOLDER_PATH = config.STATIC_DIR
os.makedirs(STATIC_FOLDER_PATH, exist_ok=True)
app.mount(f"/{config.API_PREFIX}/static", StaticFiles(directory=STATIC_FOLDER_PATH), name="static")
UPLOAD_LOCAL_FOLDER = STATIC_FOLDER_PATH + 'uploaded/'
os.makedirs(UPLOAD_LOCAL_FOLDER, exist_ok=True)
UPLOAD_URL_FOLDER = f'{config.UPLOAD_HOST_PORT}/{config.API_PREFIX}/static/uploaded/'

from openai import OpenAI

client = OpenAI(
  api_key=f'sk-{config.APIKEY}',
)

assistant = client.beta.assistants.retrieve(
    assistant_id=config.ASSISTANT_ID
)

thread = client.beta.threads.create()

def recreate_thread():
    global thread
    thread = client.beta.threads.create()


# -------------files_db-----------------

def to_file(fname, content):
    os.makedirs(os.path.join(STATIC_FOLDER_PATH, 'download'), exist_ok=True)
    with open(os.path.join(STATIC_FOLDER_PATH, 'download', fname), "w") as f:
        f.write(content)

tasks_status = {}

def save_tasks():
    with open("tasks.json", "w") as f:
        json.dump(tasks_status, f, indent=2, ensure_ascii=False)

def load_tasks():
    global tasks_status
    try:
        with open("tasks.json", "r") as f:
            tasks_status = json.load(f)
    except FileNotFoundError:
        pass


files_db: Dict[str, Dict[str, str]] = {}

def save_to_db():
    with open("files_db.json", "w") as f:
        json.dump(files_db, f, indent=2, ensure_ascii=False)

def load_db():
    global files_db
    try:
        with open("files_db.json", "r") as f:
            files_db = json.load(f)
    except FileNotFoundError:
        pass

def generate_md5(local_file_path):
    hasher = hashlib.md5()
    with open(local_file_path, 'rb') as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()

def get_existed_file_info(local_file_path):
    file_md5 = generate_md5(local_file_path)
    for file1 in files_db:
        t = files_db[file1]
        if (t['md5'] == file_md5):
            return t
    return None

# local_file_id: 'YYYYMMDD_HHMMSS.pdf'

def get_month(local_file_id):
    return local_file_id[:len('YYYYMM')]

def local_file_from_id(local_file_id):
    return os.path.join(UPLOAD_LOCAL_FOLDER, get_month(local_file_id), local_file_id)

def url_from_id(local_file_id):
    return f'{UPLOAD_URL_FOLDER}{get_month(local_file_id)}/{local_file_id}'

def get_or_upload_file(local_file_id, original_file_name = ''):
    local_file_path = local_file_from_id(local_file_id)
    info = get_existed_file_info(local_file_path)
    if info is None:
        file = client.files.create(
          file=open(local_file_path, "rb"),
          purpose='assistants'
        )
        info = {
            "original_file_name": original_file_name,
            "local_file_id": local_file_id,
            "openai_file_id": file.id,
            "size": file.bytes,
            "md5": generate_md5(local_file_path),
            "url": url_from_id(local_file_id)
        }
        files_db[local_file_id] = info
        save_to_db()
    return info

# -------------end of files_db-----------------

def ask(task_id, local_file_id_list, prompt):
    try:
        message = client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=prompt,
            file_ids=[get_or_upload_file(local_file_id).get('openai_file_id') for local_file_id in local_file_id_list]
        )
    except:
        logging.exception(f'create message failed, try to create thread')
        recreate_thread()
        message = None

    try:
        if (message is None):
            message = client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=prompt,
                file_ids=[get_or_upload_file(local_file_id).get('openai_file_id') for local_file_id in local_file_id_list]
            )

        run = client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=assistant.id,
            )

        while True:
            run = client.beta.threads.runs.retrieve(thread_id=thread.id,run_id=run.id)

            if  (task_id not in tasks_status) or (run.status != tasks_status[task_id]):
                logging.info(f'task_id={task_id}, status changed to={run.status}')

                if run.status == 'completed':
                    messages = client.beta.threads.messages.list(thread_id=thread.id).data
                    logging.info(messages[0])
                    msg_text = get_msg_text(messages[0])
                    tasks_status[task_id] = 'done_' + msg_text
                    save_tasks()
                    return
                
                if run.status in ['failed', 'cancelled', 'expired']:
                    logging.info(messages[0])
                    tasks_status[task_id] = f'done_任务失败，详细信息={run}'
                    save_tasks()
                    return

            time.sleep(3)

    except Exception as e:
        logging.exception('run failed')
        tasks_status[task_id] = f'done_任务失败，详细信息={str(e)}'
        save_tasks()
        return


def get_msg_text(message):
    message_content = message.content[0].text
    annotations = message_content.annotations
    citations = []
    now = datetime.now().strftime('%Y%m%d_%H%M%S')

    for index, annotation in enumerate(annotations):
        index = f'{now}_{index}'
        message_content.value = message_content.value.replace(annotation.text, f' [{index}]')

        if (file_citation := getattr(annotation, 'file_citation', None)):
            try:
                cited_file = client.files.retrieve(file_citation.file_id)
                citations.append(f'[{index}] 引用 {cited_file.filename}，“{file_citation.quote}”')
            except:
                logging.exception('failed to retrieve cited file')

        elif (file_path := getattr(annotation, 'file_path', None)):
            try:
                cited_file = client.files.retrieve(file_path.file_id)
                file_content = client.files.retrieve_content(file_path.file_id)
                to_file(f'{index}_{cited_file.filename}', file_content)
                citations.append(f'<{index}> 下载 {cited_file.filename}')
            except:
                logging.exception('failed to retrieve download file')

    message_content.value += '\n' + '\n'.join(citations)
    return message_content.value

# -------- fast api --------

@app.post(f"/{config.API_PREFIX}/file_list")
async def read_files():
    return list(files_db.values())


@app.post(f"/{config.API_PREFIX}/embed_file")
async def embed_file_web(local_file_id:str=Body(...), original_file_name:str=Body(...)):
    logging.info(f'local_file_id={local_file_id}, original_file_name={original_file_name}')
    info = get_or_upload_file(local_file_id, original_file_name)
    return {"local_file_id": local_file_id, "remote_file_id": info['openai_file_id']}


@app.post(f"/{config.API_PREFIX}/upload_file")
async def upload_file_web(background_tasks: BackgroundTasks, files: List[UploadFile] = File(...)):
    logging.info(f'/upload_file')
    file = files[0]
    original_file_name = file.filename
    contents = await file.read()

    file_ext = Path(original_file_name).suffix.lower()
    local_file_id = datetime.now().strftime("%Y%m%d_%H%M%S") + file_ext
    current_month = local_file_id[:len('YYYYMM')]

    directory = os.path.join(UPLOAD_LOCAL_FOLDER, current_month)
    os.makedirs(directory, exist_ok=True)
    
    local_file_path = local_file_from_id(local_file_id)
    with open(local_file_path, "wb") as f:
        f.write(contents)

    return await embed_file_web(local_file_id, original_file_name)


@app.post(f"/{config.API_PREFIX}/ask")
async def ask_web(background_tasks: BackgroundTasks, local_file_list:List[str]=Body(...), prompt:str=Body(...)):
    task_id = str(uuid.uuid4())
    tasks_status[task_id] = "in_progress"
    logging.info(f'asking, task_id={task_id}, question={prompt}, docs={local_file_list}')
    background_tasks.add_task(ask, task_id, local_file_list, prompt)
    return {"task_id": task_id}



@app.get("/" + config.API_PREFIX + "/status/{task_id}")
async def get_task_status(task_id: str):
    def event_stream():
        prev_status = None
        if task_id not in tasks_status:
            logging.error(f'task_id={task_id} not in task_status, force closing')
            yield f"data: done\n\n"
            return
        
        while not tasks_status.get(task_id).startswith("done_"):
            status = tasks_status.get(task_id)
            yield f"data: {status}\n\n"

            if (status != prev_status):
                logging.info(f'task_id={task_id}, status={status}')
                prev_status = status

            time.sleep(1)

        yield f"data: done\n\n"
    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/" + config.API_PREFIX + "/task_result/{task_id}")
async def get_task_result(task_id: str):
    if task_id not in tasks_status:
        return f"task={task_id} not found"
    if tasks_status[task_id].startswith('done_'):
        return tasks_status[task_id][len('done_'):]
    return tasks_status[task_id]


load_db()
load_tasks()

logging.info(files_db)
logging.info('====db loaded, app started====')

if __name__ == '__main__':
    # logging.info(client.beta.assistants.files.list(assistant.id))
    #ask('task_1', ['20231109_162114.txt'], '本期二级市场信用债成交规模缩减了多少')
    # cited_file = client.files.retrieve('file-af6Cip7IOaEL3n9hTL1pw3ck')
    # print(cited_file)
    # file_data = client.files.retrieve_content("file-af6Cip7IOaEL3n9hTL1pw3ck")
    # print(file_data)
    client.beta.threads.runs.cancel('run_9BrfjpbDy9uD395mYebbU026', thread_id='thread_b78RemhLTDbHYJMaufHnZt8c')