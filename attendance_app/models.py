from django.db import models

class ExcelFile(models.Model):
    file = models.FileField(upload_to='excel_files/')
