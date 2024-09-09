from supabase import create_client
from supabase.lib.client_options import ClientOptions
from sentence_transformers import SentenceTransformer
import replicate
import vecs
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

key = os.getenv("key")
url = os.getenv("url")
opts = ClientOptions().replace(schema="vecs")
client = create_client(url, key, options=opts)

user = os.getenv("user")
password = os.getenv("password")
host = os.getenv("host")
port = os.getenv("port")
db_name = "postgres"
DB_CONNECTION = f"postgresql://{user}:{password}@{host}:{port}/{db_name}"
vx = vecs.create_client(DB_CONNECTION)
query_embeds = vx.get_or_create_collection(name="docs", dimension=768)
model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')

def find_prediction(prediction_list, id):
  for item in prediction_list:
    temp_dict = dict(item)
    if temp_dict.get("id") == id:
      return temp_dict

def find_id(prediction_list, inp):
  id = ""
  for item in prediction_list:
    temp_dict = dict(item)
    if temp_dict.get("input").get("prompt") == inp:
      id = temp_dict.get("id")
      break
    else:
      pass
  return id

def live_inference(prompt, max_new_tokens = 1024, top_k = 50, top_p = 0.9, temperature = 0.6, presence_penalty=1.15):
  output = replicate.run(
      "meta/meta-llama-3-8b-instruct",
      input={
          "top_k": top_k,
          "top_p": top_p,
          "prompt": prompt,
          "temperature": temperature,
          "max_new_tokens": max_new_tokens,
          "prompt_template": "{prompt}",
          "frequency_penalty": presence_penalty,
          "seed": 61001
      })

  id = find_id(replicate.predictions.list(), prompt)
  generating = True
  out = ""
  while generating:
    prediction_list = replicate.predictions.list()
    prediction = find_prediction(prediction_list, id)
    try:
      if prediction.get("status") != "succeeded":
          pass
      else:
        for item in prediction.get("output"):
          out += item
        generating = False
    except:
      pass
  return out


def query_db(query, limit = 5, filters = {}, measure = "cosine_distance", include_value = False, include_metadata=False, table = "2023"):
  query_embeds = vx.get_or_create_collection(name= table, dimension=768)
  ans = query_embeds.query(
      data=query,
      limit=limit,
      filters=filters,
      measure=measure,
      include_value=include_value,
      include_metadata=include_metadata,
  )
  return ans  

def construct_result(ans):
  ans.sort(key=sort_by_score, reverse=True)
  results = ""
  for i in range(0, len(ans)):
    a, b = ans[i][2].get("sentencia"), ans[i][2].get("fragmento")
    results += (f"En la sentencia {a}, se dijo {b}\n")
  return results

def sort_by_score(item):
  return item[1]

def referencias(results):
  references = 'Sentencias encontradas: \n'
  enlistadas = []
  for item in results: 
    if item[2].get('sentencia') in enlistadas: 
      pass
    else: 
      references += item[2].get('sentencia')+ ' '
      enlistadas.append(item[2].get('sentencia'))
  return references

def inference(prompt):
  encoded_prompt = model.encode(prompt)
  years = range(2020, 2025)
  results = []
  for year in years:
    results.extend(query_db(encoded_prompt, include_metadata = True, table = str(year), include_value=True, limit = 3))
  results.sort(key=sort_by_score, reverse=True)
  context =f"""
  <|begin_of_text|>
  <|start_header_id|>system<|end_header_id|>
  Eres Ticio, un asistente de investigación jurídica. Tu deber es organizar el contenido de las sentencias de la jurisprudencia de acuerdo 
  a las necesidades del usuario. Debes responder solo en español. Debes responder solo en base a la información del contexto a continuación.
  Siempre debes mencionar la fuente en tu escrito, debe tener un estilo formal y juridico.
  Contexto: 
  {construct_result(results)}
  <|eot_id|>
  <|start_header_id|>user<|end_header_id|>
  {prompt}
  <|eot_id|>
  <|start_header_id|>assistant<|end_header_id|>
  """
  return live_inference(context, max_new_tokens=512) + '\n' + referencias(results)
