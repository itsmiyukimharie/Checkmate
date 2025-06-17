class SessionHelper:
    """Helper class for session operations"""
    
    @staticmethod
    def store_temp_test_data(request, test_data):
        """Store temporary test data in session"""
        request.session['temp_test_data'] = test_data
    
    @staticmethod
    def get_temp_test_data(request):
        """Get temporary test data from session"""
        return request.session.get('temp_test_data')
    
    @staticmethod
    def clear_temp_test_data(request):
        """Clear temporary test data from session"""
        if 'temp_test_data' in request.session:
            del request.session['temp_test_data']
