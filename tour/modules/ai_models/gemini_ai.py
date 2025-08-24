import google.generativeai as genai
from .ai_service import AIService


class GeminiModel(AIService):

    def get_ai_comment(self, system_text='', content_text='', **kwargs):

        genai.configure(api_key=self.ai_service_key)

        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(
            contents=system_text + content_text,
        )
        print(response.text)
        return response.text.replace('```json', '').replace('```', '')