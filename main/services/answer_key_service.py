import csv
from django.shortcuts import get_object_or_404
from django.http import HttpResponse, JsonResponse
from ..models import TestInformation, TestAnswerKey

class AnswerKeyService:
    """Service class for answer key operations"""
    
    @staticmethod
    def get_user_tests(user):
        """Get all tests for a user with related answer keys"""
        return TestInformation.objects.filter(user=user).prefetch_related('answer_keys')
    
    @staticmethod
    def create_temp_test_data(form_data):
        """Create temporary test data for session storage"""
        return {
            'test_name': form_data['test_name'],
            'test_type': form_data['test_type'],
            'question_count': form_data['question_count']
        }
    
    @staticmethod
    def create_temp_test_object(temp_data):
        """Create temporary test object (not saved to DB)"""
        return TestInformation(
            test_name=temp_data['test_name'],
            test_type=temp_data['test_type'],
            question_count=temp_data['question_count']
        )
    
    @staticmethod
    def get_test_by_id(test_id, user):
        """Get test by ID for specific user"""
        return get_object_or_404(TestInformation, id=test_id, user=user)
    
    @staticmethod
    def save_test_to_db(test_info, user):
        """Save test to database"""
        test_info.user = user
        test_info.name = test_info.test_name
        test_info.status = 'draft'
        test_info.save()
        return test_info
    
    @staticmethod
    def save_answers(test_info, form_data):
        """Save answers for a test"""
        # Delete existing answers
        TestAnswerKey.objects.filter(test_information=test_info).delete()
        
        # Save new answers
        answer_keys = []
        for i in range(1, test_info.question_count + 1):
            answer_key = TestAnswerKey(
                test_information=test_info,
                question_number=i,
                answer=form_data[f'question_{i}']
            )
            answer_keys.append(answer_key)
        
        TestAnswerKey.objects.bulk_create(answer_keys)
        return len(answer_keys)
    
    @staticmethod
    def get_existing_answers(test_info):
        """Get existing answers as initial data for form"""
        existing_answers = TestAnswerKey.objects.filter(test_information=test_info)
        initial_data = {}
        for answer_key in existing_answers:
            initial_data[f'question_{answer_key.question_number}'] = answer_key.answer
        return initial_data
    
    @staticmethod
    def delete_test(test_id, user):
        """Delete a test and return test name"""
        test_info = get_object_or_404(TestInformation, id=test_id, user=user)
        test_name = test_info.test_name
        test_info.delete()
        return test_name
    
    @staticmethod
    def get_test_with_answers(test_id, user):
        """Get test with all answers for printing/exporting"""
        test_info = get_object_or_404(TestInformation, id=test_id, user=user)
        answer_keys = TestAnswerKey.objects.filter(test_information=test_info).order_by('question_number')
        return test_info, answer_keys
    
    # Export Methods
    @staticmethod
    def generate_csv_response(test_info, answer_keys):
        """Generate CSV response for answer key export"""
        response = HttpResponse(content_type='text/csv')
        filename = f"answer_key_{test_info.test_name.replace(' ', '_')}.csv"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        writer = csv.writer(response)
        
        # Write structured header for machine processing
        AnswerKeyService._write_csv_header(writer, test_info)
        AnswerKeyService._write_csv_data(writer, test_info, answer_keys)
        AnswerKeyService._write_csv_metadata(writer, test_info, answer_keys)
        AnswerKeyService._write_csv_mapping(writer, test_info)
        
        return response
    
    @staticmethod
    def _write_csv_header(writer, test_info):
        """Write CSV header section"""
        writer.writerow(['# CheckMate Answer Key - Machine Readable Format'])
        writer.writerow(['# Test Name:', test_info.test_name])
        writer.writerow(['# Test Type:', test_info.test_type])
        writer.writerow(['# Question Count:', test_info.question_count])
        writer.writerow(['# Answer Choices:', ','.join(test_info.get_answer_choices())])
        writer.writerow(['# Created:', test_info.created_at.isoformat()])
        writer.writerow(['# Generated:', test_info.updated_at.isoformat()])
        writer.writerow([])  # Empty row separator
    
    @staticmethod
    def _write_csv_data(writer, test_info, answer_keys):
        """Write CSV answer data section"""
        writer.writerow(['question_number', 'correct_answer', 'answer_index'])
        
        answer_choices = test_info.get_answer_choices()
        
        if answer_keys:
            for answer_key in answer_keys:
                try:
                    answer_index = answer_choices.index(answer_key.answer)
                except ValueError:
                    answer_index = -1  # Invalid answer
                
                writer.writerow([
                    answer_key.question_number,
                    answer_key.answer,
                    answer_index
                ])
        else:
            # Write placeholder for empty answer key
            for i in range(1, test_info.question_count + 1):
                writer.writerow([i, '', -1])
    
    @staticmethod
    def _write_csv_metadata(writer, test_info, answer_keys):
        """Write CSV metadata section"""
        writer.writerow([])
        writer.writerow(['# Metadata for Verification'])
        writer.writerow(['# Total Questions Expected:', test_info.question_count])
        writer.writerow(['# Total Answers Provided:', len(answer_keys)])
        writer.writerow(['# Answer Choice Count:', len(test_info.get_answer_choices())])
        writer.writerow(['# Format Version:', '1.0'])
        writer.writerow(['# Compatible with CheckMate Image Processing'])
    
    @staticmethod
    def _write_csv_mapping(writer, test_info):
        """Write CSV answer choice mapping section"""
        writer.writerow([])
        writer.writerow(['# Answer Choice Mapping'])
        writer.writerow(['index', 'choice', 'display'])
        for i, choice in enumerate(test_info.get_answer_choices()):
            display = 'T' if choice == 'True' else 'F' if choice == 'False' else choice
            writer.writerow([i, choice, display])
    
    @staticmethod
    def generate_print_data(test_info, answer_keys):
        """Generate data structure for JSON printing"""
        return {
            'test_info': {
                'test_name': test_info.test_name,
                'test_type_display': test_info.get_test_type_display(),
                'question_count': test_info.question_count,
                'created_at': test_info.created_at.isoformat(),
            },
            'answer_keys': [
                {
                    'question_number': ak.question_number,
                    'answer': ak.answer
                }
                for ak in answer_keys
            ],
            'answer_choices': test_info.get_answer_choices()
        }
