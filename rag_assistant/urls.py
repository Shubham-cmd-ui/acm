from django.urls import path
from . import views

app_name = 'rag_assistant'

urlpatterns = [
    path('', views.index_view, name='index'),
    path('upload/', views.upload_document_view, name='upload_document'),
    path('api/query/', views.query_document_view, name='query_document'),
    path('api/documents/', views.document_list_view, name='document_list'),
    path('api/documents/<uuid:doc_id>/history/', views.document_history_view, name='document_history'),
    path('api/documents/<uuid:doc_id>/delete/', views.delete_document_view, name='document_delete'),
    path('api/documents/<uuid:doc_id>/study-materials/', views.get_study_materials_view, name='get_study_materials'),
    path('api/documents/<uuid:doc_id>/study-materials/generate/', views.generate_study_materials_view, name='generate_study_materials'),
    path('api/documents/<uuid:doc_id>/quiz/generate/', views.generate_quiz_view, name='generate_quiz'),
    path('api/documents/<uuid:doc_id>/quiz/submit/', views.submit_quiz_view, name='submit_quiz'),
    path('api/documents/<uuid:doc_id>/quiz/history/', views.quiz_history_view, name='quiz_history'),
]
