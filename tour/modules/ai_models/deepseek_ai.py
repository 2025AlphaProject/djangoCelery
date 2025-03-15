from openai import OpenAI
from .ai_service import AIService

class DeepseekModel(AIService):
    def get_ai_comment(self, system_text='', content_text='', **kwargs):
        system = system_text
        content = content_text
        client = OpenAI(api_key=self.ai_service_key, base_url="https://api.deepseek.com")
        message = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ], stream=False
        )
        return message.choices[0].message.content