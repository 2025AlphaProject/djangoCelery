import anthropic
from anthropic.types import MessageParam

from .ai_service import AIService
class ClaudeModel(AIService):
    def get_ai_comment(self, system_text='', content_text='', **kwargs):
        system = system_text
        content = content_text
        client = anthropic.Anthropic(api_key=self.ai_service_key)
        message = client.messages.create(
            model='claude-4-opus-20250514',
            max_tokens=1000,
            system=system,
            messages=MessageParam(content=content, role='user')
        )
        print(message.content[0].text)
        return message.content[0].text