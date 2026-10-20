from django import forms

from apps.courses.models import Course
from apps.universities.models import University

from .models import Student


class StudentRegistrationForm(forms.ModelForm):
    """
    Form used by franchise owners / staff to register a new student.

    The `franchise` and `created_by` fields are set in the view,
    never exposed in the form HTML, to prevent parameter-tampering.
    """

    class Meta:
        model = Student

        fields = [
            "full_name",
            "guardian_name",
            "date_of_birth",
            "gender",
            "mobile",
            "email",
            "address",
            "profile_image",
            "course",
            "university",
            "study_mode",
            "previous_qualification",
            "admission_date",
            "admission_status",
            "fee_status",
            "remarks",
        ]

        widgets = {
            "profile_image": forms.FileInput(
                attrs={"accept": "image/jpeg,image/png,image/webp"}
            ),
            "date_of_birth": forms.DateInput(
                attrs={"type": "date"},
                format="%Y-%m-%d",
            ),
            "admission_date": forms.DateInput(
                attrs={"type": "date"},
                format="%Y-%m-%d",
            ),
            "address": forms.Textarea(attrs={"rows": 3}),
            "remarks": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Only active courses and universities in dropdowns
        self.fields["course"].queryset = Course.objects.filter(
            active=True
        ).order_by("name")
        self.fields["university"].queryset = University.objects.filter(
            active=True
        ).order_by("name")

        # Make non-essential fields not required in the form
        for field_name in [
            "guardian_name",
            "date_of_birth",
            "gender",
            "email",
            "address",
            "previous_qualification",
            "admission_date",
            "remarks",
        ]:
            self.fields[field_name].required = False


class StudentEditForm(forms.ModelForm):
    """
    Restricted edit form.  Franchise staff can update a limited set of
    fields; they cannot change which franchise the student belongs to.
    """

    class Meta:
        model = Student

        fields = [
            "full_name",
            "guardian_name",
            "date_of_birth",
            "gender",
            "mobile",
            "email",
            "address",
            "profile_image",
            "course",
            "university",
            "study_mode",
            "previous_qualification",
            "admission_date",
            "admission_status",
            "fee_status",
            "remarks",
        ]

        widgets = {
            "profile_image": forms.FileInput(
                attrs={"accept": "image/jpeg,image/png,image/webp"}
            ),
            "date_of_birth": forms.DateInput(
                attrs={"type": "date"},
                format="%Y-%m-%d",
            ),
            "admission_date": forms.DateInput(
                attrs={"type": "date"},
                format="%Y-%m-%d",
            ),
            "address": forms.Textarea(attrs={"rows": 3}),
            "remarks": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        courses = Course.objects.filter(active=True)
        universities = University.objects.filter(active=True)
        if self.instance.pk:
            courses = courses | Course.objects.filter(pk=self.instance.course_id)
            universities = universities | University.objects.filter(
                pk=self.instance.university_id
            )
        self.fields["course"].queryset = courses.order_by("name")
        self.fields["university"].queryset = universities.order_by("name")

        for field_name in [
            "guardian_name",
            "date_of_birth",
            "gender",
            "email",
            "address",
            "previous_qualification",
            "admission_date",
            "remarks",
        ]:
            self.fields[field_name].required = False


class StudentSearchForm(forms.Form):
    """Filter/search form for the student list page."""

    q = forms.CharField(
        required=False,
        label="Search",
        widget=forms.TextInput(
            attrs={"placeholder": "Name, reg. no. or mobile…"}
        ),
    )
    course = forms.ModelChoiceField(
        queryset=Course.objects.order_by("name"),
        required=False,
        empty_label="All Courses",
    )
    university = forms.ModelChoiceField(
        queryset=University.objects.order_by("name"),
        required=False,
        empty_label="All Universities",
    )
    study_mode = forms.ChoiceField(
        choices=[("", "All Modes")] + Student.STUDY_MODE_CHOICES,
        required=False,
    )
    admission_status = forms.ChoiceField(
        choices=[("", "All Statuses")] + Student.ADMISSION_STATUS_CHOICES,
        required=False,
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        label="From Date",
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        label="To Date",
    )
