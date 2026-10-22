from django.contrib import admin
from .models import Document, DocumentChunk, ChatMessage, StudyMaterial, QuizAttempt

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('original_filename', 'file_type', 'formatted_size', 'total_chunks', 'total_pages', 'uploaded_at')
    list_filter = ('file_type', 'uploaded_at')
    search_fields = ('original_filename', 'id')
    readonly_fields = ('id', 'uploaded_at', 'total_chunks', 'total_pages', 'index_filename')

@admin.register(DocumentChunk)
class DocumentChunkAdmin(admin.ModelAdmin):
    list_display = ('document', 'chunk_index', 'page_number', 'content_preview')
    list_filter = ('document', 'page_number')
    search_fields = ('content', 'document__original_filename')

    def content_preview(self, obj):
        return obj.content[:80] + "..." if len(obj.content) > 80 else obj.content
    content_preview.short_description = "Chunk Content"

@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('document', 'question_preview', 'is_grounded', 'created_at')
    list_filter = ('is_grounded', 'document')
    search_fields = ('question', 'answer')

    def question_preview(self, obj):
        return obj.question[:50] + "..." if len(obj.question) > 50 else obj.question
    question_preview.short_description = "Question"

@admin.register(StudyMaterial)
class StudyMaterialAdmin(admin.ModelAdmin):
    list_display = ('document', 'flashcards_count', 'quiz_count', 'updated_at')
    readonly_fields = ('created_at', 'updated_at')

    def flashcards_count(self, obj):
        return len(obj.flashcards)
    flashcards_count.short_description = "Flashcards"

    def quiz_count(self, obj):
        return len(obj.quiz)
    quiz_count.short_description = "Quiz Questions"

@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ('document', 'score_display', 'percentage_display', 'difficulty', 'target_topic', 'created_at')
    list_filter = ('difficulty', 'created_at')
    readonly_fields = ('created_at',)

    def score_display(self, obj):
        return f"{obj.score}/{obj.total_questions}"
    score_display.short_description = "Score"

    def percentage_display(self, obj):
        return f"{obj.percentage:.0f}%"
    percentage_display.short_description = "Accuracy"
