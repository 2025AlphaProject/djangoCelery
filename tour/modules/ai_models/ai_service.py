from abc import ABC, abstractmethod
class AIService(ABC):
    def __init__(self, ai_service_key=None):
        self.ai_service_key = ai_service_key
    @abstractmethod
    def get_ai_comment(self, system_text='', content_text='', **kwargs):
        pass

def get_ai_response(model: AIService, system_text='', content_text='', **kwargs):
    return model.get_ai_comment(system_text, content_text, **kwargs)