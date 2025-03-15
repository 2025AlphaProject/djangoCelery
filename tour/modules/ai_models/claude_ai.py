import anthropic
from .ai_service import AIService
class ClaudeModel(AIService):
    def get_ai_comment(self, system_text='', content_text='', **kwargs):
        system = system_text
        content = content_text
        client = anthropic.Anthropic(api_key=self.ai_service_key)
        message = client.messages.create(
            model='claude-3-7-sonnet-20250219',
            max_tokens=20000,
            system=system,
            messages=[
                {
                    "role": 'user',
                    "content": [
                        {
                            'type': 'text',
                            'text': content,
                        }
                    ]
                }
            ]
        )
        print(message.content[0].text)
        return message.content[0].text