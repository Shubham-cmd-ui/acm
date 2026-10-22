import os
import uuid
from django.db import models
from django.conf import settings

class Document(models.Model):
    """
    Represents an uploaded document (PDF or TXT) indexed for RAG.
    Each document owns its dedicated FAISS vector index file.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.FileField(upload_to='documents/')
    original_filename = models.CharField(max_length=255)
    file_type = models.CharField(max_length=10)  # 'pdf' or 'txt'
    file_size_bytes = models.BigIntegerField()
    uploaded_at = models.DateTimeField(auto_now_add=True)
    total_pages = models.IntegerField(default=1)
    total_chunks = models.IntegerField(default=0)
    index_filename = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.original_filename} ({self.file_type.upper()}) - {self.total_chunks} chunks"

    @property
    def formatted_size(self):
        """Format file size in KB or MB."""
        size_kb = self.file_size_bytes / 1024
        if size_kb < 1024:
            return f"{size_kb:.1f} KB"
        return f"{size_kb / 1024:.2f} MB"

    def get_index_path(self):
        """Return the filesystem path to the document's FAISS index."""
        return os.path.join(settings.VECTOR_INDEX_DIR, f"{self.id}.faiss")

    def delete(self, *args, **kwargs):
        """Clean up underlying file and FAISS vector index on deletion."""
        index_path = self.get_index_path()
        if os.path.exists(index_path):
            try:
                os.remove(index_path)
            except OSError:
                pass

        if self.file and os.path.exists(self.file.path):
            try:
                os.remove(self.file.path)
            except OSError:
                pass

        super().delete(*args, **kwargs)


class DocumentChunk(models.Model):
    """
    Individual chunk of extracted text belonging to a document.
    Indexed by chunk_index matching the FAISS vector index row ID.
    """
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='chunks')
    chunk_index = models.IntegerField(help_text="0-indexed position in vector index")
    content = models.TextField(help_text="Extracted text chunk content")
    page_number = models.IntegerField(null=True, blank=True, help_text="Page number in original document")
    char_start = models.IntegerField(null=True, blank=True)
    char_end = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ['document', 'chunk_index']
        unique_together = ('document', 'chunk_index')

    def __str__(self):
        page_str = f" [p.{self.page_number}]" if self.page_number else ""
        return f"Doc {self.document_id} Chunk #{self.chunk_index}{page_str}"


class ChatMessage(models.Model):
    """
    Persisted question-and-answer interaction grounded in document chunks.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='chat_messages')
    question = models.TextField()
    answer = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_grounded = models.BooleanField(default=True)
    retrieved_sources = models.JSONField(
        default=list,
        help_text="List of source passages: [{chunk_index, page_number, score, excerpt}]"
    )

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Q: {self.question[:40]}... (Doc: {self.document.original_filename})"


class StudyMaterial(models.Model):
    """
    Cached AI-generated study aids derived from the document:
    - Flashcards (terms, Q&A, definitions)
    - Short Notes (executive summary, key takeaways, breakdown)
    - Important Topics (core themes, importance level, key concepts)
    - Interactive Quiz (multiple choice questions with answers and explanations)
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.OneToOneField(Document, on_delete=models.CASCADE, related_name='study_material')
    flashcards = models.JSONField(default=list, help_text="[{front, back, category}]")
    short_notes = models.JSONField(default=dict, help_text="{summary, key_takeaways, sections}")
    important_topics = models.JSONField(default=list, help_text="[{title, importance, overview, key_points}]")
    quiz = models.JSONField(default=list, help_text="[{id, question, options, correct_index, explanation, topic}]")
    seen_quiz_questions = models.JSONField(default=list, help_text="List of previously generated question texts to avoid repetition")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Study Material for {self.document.original_filename}"


class QuizAttempt(models.Model):
    """
    Tracks individual quiz attempts, topic-wise accuracy, weak topic diagnostics,
    and historical performance over time.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='quiz_attempts')
    score = models.IntegerField(help_text="Number of questions answered correctly")
    total_questions = models.IntegerField(help_text="Total number of questions in attempt")
    percentage = models.FloatField(help_text="Accuracy percentage")
    difficulty = models.CharField(max_length=50, default='mixed')
    target_topic = models.CharField(max_length=255, blank=True, null=True, help_text="Specific topic if practice quiz")
    topic_scores = models.JSONField(default=dict, help_text="{topic_name: {correct, total, percentage}}")
    weak_topics = models.JSONField(default=list, help_text="[{topic, accuracy, reason, recommendation}]")
    recommendations = models.JSONField(default=list, help_text="List of actionable recommendations")
    questions_snapshot = models.JSONField(default=list, help_text="Snapshot of questions served in this attempt")
    user_answers = models.JSONField(default=dict, help_text="{question_id: selected_index}")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Attempt {self.percentage:.0f}% ({self.score}/{self.total_questions}) - {self.document.original_filename}"
