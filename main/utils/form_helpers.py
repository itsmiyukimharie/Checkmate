from ..forms import CreateAnswerKeyForm, AnswerKeyEntryForm

class FormHelper:
    """Helper class for form operations"""
    
    @staticmethod
    def create_answer_key_form(request_data=None):
        """Create answer key form instance"""
        return CreateAnswerKeyForm(request_data)
    
    @staticmethod
    def create_answer_entry_form(test_info, request_data=None, initial_data=None):
        """Create answer entry form with proper configuration"""
        answer_choices = test_info.get_answer_choices()
        
        form_kwargs = {
            'question_count': test_info.question_count,
            'answer_choices': answer_choices
        }
        
        if initial_data:
            form_kwargs['initial'] = initial_data
            
        return AnswerKeyEntryForm(request_data, **form_kwargs)
