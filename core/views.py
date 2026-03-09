from rest_framework import viewsets, status, generics
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.response import Response
from django.core.exceptions import ValidationError
from .models import *
from .serializers import *
from rest_framework.permissions import IsAuthenticated
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate
from django.db.models import Count, Q
from rest_framework.authentication import BaseAuthentication
from rest_framework import exceptions
from .models import *


# User Registration View
class RegisterUserView(generics.CreateAPIView):
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)
        return Response({
            "id": user.id,
            # "national_id": user.national_id,
            # "first_name": user.first_name,
            # "last_name": user.last_name,
            "role": user.role,
            # "password": user._temp_password,
            "token": token.key,
            "message": "User registered successfully"
        }, status=status.HTTP_201_CREATED)


# register hospital
class HospitalRegisterView(generics.GenericAPIView):
    serializer_class = HospitalRegisterSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        hospital = serializer.save()
        hospital.set_password(request.data['password'])
        hospital.save()  # مهم نحفظ الباسورد بعد التغيير

        hospital_data = {
            "id": hospital.id,
            "name": hospital.name,
            "hospital_type": hospital.hospital_type,
            "location": hospital.location,
            "license_number": hospital.license_number,
            "phone": hospital.phone,
            "emergency_phone": hospital.emergency_phone,
            "email": hospital.email,
            "working_hours": hospital.working_hours,
        }

        return Response({
            "message": "Hospital registered successfully",
            "hospital": hospital_data
        }, status=status.HTTP_201_CREATED)


# login users and hospitals
class UnifiedLoginView(APIView):
    def post(self, request):
        serializer = UnifiedLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if serializer.validated_data["type"] == "hospital":
            hospital = serializer.validated_data["hospital"]
            token = serializer.validated_data["token"]

            return Response({
                "type": "hospital",
                "id": hospital.id,
                "name": hospital.name,
                "hospital_type": hospital.hospital_type,
                "token": token,
                "message": "تم تسجيل الدخول كمستشفى بنجاح"
            })

        else:
            user = serializer.validated_data["user"]
            token = serializer.validated_data["token"]

            return Response({
                "type": "user",
                "id": user.id,
                "role": user.role,
                "token": token,
                "message": "تم تسجيل الدخول كمستخدم بنجاح"
            })


# logout view
class LogoutUserView(APIView):
    # permission_classes = [IsAuthenticated]

    def post(self, request):
        if hasattr(request.user, "auth_token"):
            request.user.auth_token.delete()

        return Response({"message": "Logged out successfully"})


# user viewset
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

    # 🔹 إحصائيات عامة لكل users
    @action(detail=False, methods=['get'])
    def stats(self, request):
        stats = User.objects.aggregate(
            total_users=Count('id'),
            patients_count=Count('id', filter=Q(role='patient')),
            donors_count=Count('id', filter=Q(role='donor')),
        )
        return Response(stats)

    # 🔹 إحصائيات حسب مستشفى
    @action(detail=False, methods=['get'])
    def stats_by_hospital(self, request):
        hospital_id = request.query_params.get('hospital')
        qs = User.objects.all()
        if hospital_id:
            qs = qs.filter(hospital_id=hospital_id)

        return Response({
            "total_users": qs.count(),
            "patients": qs.filter(role='patient').count(),
            "donors": qs.filter(role='donor').count(),
        })

    # 🔹 كل المستخدمين مع التفاصيل الكاملة (patients + donors)
    @action(detail=False, methods=['get'])
    def stats_all(self, request):
        patients_qs = User.objects.filter(role='patient')
        donors_qs = User.objects.filter(role='donor')

        # استخدام UserSerializer اللي فيه كل بيانات profile
        patients_data = UserSerializer(patients_qs, many=True).data
        donors_data = UserSerializer(donors_qs, many=True).data

        return Response({
            "total_patients": patients_qs.count(),
            "total_donors": donors_qs.count(),
            "patients": patients_data,
            "donors": donors_data
        })


class PatientMedicalProfileListView(generics.ListAPIView):
    queryset = PatientMedicalProfile.objects.all()
    serializer_class = PatientMedicalProfileSerializer


class DonorMedicalProfileListView(generics.ListAPIView):
    queryset = DonorMedicalProfile.objects.all()
    serializer_class = DonorMedicalProfileSerializer


class PatientMedicalProfileViewSet(viewsets.ModelViewSet):
    queryset = PatientMedicalProfile.objects.all()
    serializer_class = PatientMedicalProfileSerializer


class DonorMedicalProfileViewSet(viewsets.ModelViewSet):
    queryset = DonorMedicalProfile.objects.all()
    serializer_class = DonorMedicalProfileSerializer


class HospitalViewSet(viewsets.ModelViewSet):
    queryset = Hospital.objects.all()
    serializer_class = HospitalFullSerializer


class DoctorViewSet(viewsets.ModelViewSet):
    queryset = Doctor.objects.all()
    serializer_class = DoctorSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        hospital_id = self.request.query_params.get("hospital")
        if hospital_id:
            queryset = queryset.filter(hospital_id=hospital_id)
        return queryset


class ChronicDiseaseViewSet(viewsets.ModelViewSet):
    queryset = ChronicDisease.objects.all()
    serializer_class = ChronicDiseaseSerializer


class UserChronicDiseaseViewSet(viewsets.ModelViewSet):
    queryset = UserChronicDisease.objects.all()
    serializer_class = UserChronicDiseaseSerializer


class AppointmentViewSet(viewsets.ModelViewSet):
    queryset = Appointment.objects.all()
    serializer_class = AppointmentSerializer

    def perform_create(self, serializer):
        doctor = serializer.validated_data.get('doctor')
        hospital = serializer.validated_data.get('hospital')
        if doctor and hospital and doctor.hospital != hospital:
            raise ValidationError("Doctor must belong to selected hospital")
        serializer.save()


# class OrganMatchingViewSet(viewsets.ModelViewSet):
#     queryset = OrganMatching.objects.all()
#     serializer_class = OrganMatchingSerializer

#     @action(detail=False, methods=['post'])
#     def auto_match(self, request):
#         patients = User.objects.filter(role='patient', status='جاهز')
#         all_matches = []
#         for patient in patients:
#             donors = User.objects.filter(role='donor', status='جاهز')

#         for patient in patients:
#             for donor in donors:
#                 result = OrganMatching.calculate_match(patient, donor)

#                 match, created = OrganMatching.objects.update_or_create(
#                     patient=patient,
#                     donor=donor,
#                     defaults={
#                         "organ_type": getattr(patient.patient_profile, 'organ_needed', 'N/A'),
#                         "match_percentage": result['match_percentage'],
#                         "ai_result": result['ai_result'],
#                         "status": " قيد التحليل "
                        
#                     }
#                 )
#                 all_matches.append({
#                     "patient": str(patient),
#                     "donor": str(donor),
#                     "organ_type": getattr(patient.patient_profile, 'organ_needed', 'N/A'),
#                     "match_percentage": result['match_percentage']
#                 })
#         return Response(all_matches)

class OrganMatchingViewSet(viewsets.ModelViewSet):
    queryset = OrganMatching.objects.all()
    serializer_class = OrganMatchingSerializer

    @action(detail=False, methods=['post'])
    def auto_match(self, request):
        patients = User.objects.filter(role='patient', status='جاهز')
        all_matches = []
        for patient in patients:
            donors = User.objects.filter(role='donor', status='جاهز')

        for patient in patients:
            for donor in donors:
                result = OrganMatching.calculate_match(patient, donor)

                match, created = OrganMatching.objects.update_or_create(
                    patient=patient,
                    donor=donor,
                    defaults={
                        "organ_type": getattr(patient.patient_profile, 'organ_needed', 'N/A'),
                        "match_percentage": result['match_percentage'],
                        "ai_result": result['ai_result'],
                        "status": " قيد التحليل "
                        
                    }
                )
                all_matches.append({
                    "patient": str(patient),
                    "donor": str(donor),
                    "organ_type": getattr(patient.patient_profile, 'organ_needed', 'N/A'),
                    "match_percentage": result['match_percentage']
                })
        return Response(all_matches)



class SurgeryViewSet(viewsets.ModelViewSet):
    queryset = Surgery.objects.all()
    serializer_class = SurgerySerializer


class MRIReportViewSet(viewsets.ModelViewSet):
    queryset = MRIReport.objects.all()
    serializer_class = MRIReportSerializer


# class UserReportViewSet(viewsets.ModelViewSet):
#     queryset = UserReport.objects.all()
#     serializer_class = UserReportSerializer
#
#     def get_queryset(self):
#         user = getattr(self.request, 'user', None)
#         if user and not user.is_anonymous:
#             return UserReport.objects.filter(patient=user).order_by('-created_at')
#
#         return UserReport.objects.none()
#
#     def perform_create(self, serializer):
#         user = self.request.user
#
#         if user.is_anonymous:
#             raise ValidationError("Authentication required")
#
#         serializer.save(patient=user)
#




class UserReportViewSet(viewsets.ModelViewSet):
    queryset = UserReport.objects.all()
    serializer_class = UserReportSerializer

    def get_queryset(self):
        user = getattr(self.request, 'user', None)
        if user and not user.is_anonymous:
            # لو في مستخدم مسجل، جِب تقاريره فقط
            return UserReport.objects.filter(patient=user).order_by('-created_at')
        # لو مفيش مستخدم مسجل، رجع فاضي
        return UserReport.objects.none()

    def perform_create(self, serializer):
        user = getattr(self.request, 'user', None)
        if user and not user.is_anonymous:
            # لو مستخدم مسجل، اربط التقرير به
            serializer.save(patient=user)
        else:
            # لو مفيش، خلي الـ patient لازم يُرسل في البيانات
            serializer.save()
class SurgeryReportViewSet(viewsets.ModelViewSet):
    queryset = SurgeryReport.objects.select_related(
        'surgery__organ_matching__patient',
        'surgery__doctor',
        'surgery__hospital'
    )
    serializer_class = SurgeryReportSerializer

    def perform_create(self, serializer):
        report = serializer.save()

        # 🔔 Alert للمريض
        patient = report.surgery.organ_matching.patient
        Alert.objects.create(
            user=patient,
            message=f"تم إضافة تقرير العملية الجراحية الخاصة بك: {report.surgery.surgery_number}",
            alert_type='طبي'
        )

        # 🔔 Alert للمستشفى
        hospital = getattr(report.surgery, "hospital", None)
        if hospital:
            AlertHospital.objects.create(
                hospital=hospital,
                message=f"تم إضافة تقرير عملية {report.surgery.surgery_number}.",
                alert_type='معلومة'
            )

        # 📊 تحديث أولوية المريض
        priority, created = PatientPriority.objects.get_or_create(patient=patient)
        priority.score += 10
        if priority.score >= 80:
            priority.level = 'حرجة جداً'
        elif priority.score >= 50:
            priority.level = 'اولوليه عاليه'
        elif priority.score >= 20:
            priority.level = 'اولوليه متوسطة'
        else:
            priority.level = 'اولوليه منخفضه'
        priority.save()


class PatientPriorityViewSet(viewsets.ModelViewSet):
    queryset = PatientPriority.objects.all()
    serializer_class = PatientPrioritySerializer

    @action(detail=False, methods=['post'])
    def calculate_priority(self, request):
        patients = User.objects.filter(role='patient')
        results = []
        for patient in patients:
            score = 0
            if patient.chronic_diseases.exists():
                score += patient.chronic_diseases.count() * 10
            if hasattr(patient, 'patient_profile') and patient.patient_profile.organ_needed:
                score += 20

            # تحديد المستوى
            level = 'low'
            if score >= 50:
                level = 'critical'
            elif score >= 30:
                level = 'high'
            elif score >= 10:
                level = 'medium'

            # حفظ أو تحديث
            priority, _ = PatientPriority.objects.update_or_create(
                patient=patient,
                defaults={'score': score, 'level': level}
            )

            results.append({
                "patient": str(patient),
                "score": score,
                "level": level
            })

        return Response(results)

class DonorHealthViewSet(viewsets.ModelViewSet):
    queryset = DonerHealth.objects.all()
    serializer_class = DonerHealthSerializer
# class AlertViewSet(viewsets.ModelViewSet):
#     queryset = Alert.objects.all()
#     serializer_class = AlertSerializer

#     def get_queryset(self):
#         return Alert.objects.filter(user=self.request.user).order_by('-created_at')  # مؤقتًا بدون auth

#     @action(detail=True, methods=['post'])
#     def mark_read(self, request, pk=None):
#         alert = self.get_object()
#         alert.read = True
#         alert.save()
#         return Response({"detail": "Alert marked as read"})
class AlertViewSet(viewsets.ModelViewSet):
    queryset = Alert.objects.all()
    serializer_class = AlertSerializer
    permission_classes = [IsAuthenticated]  # 🔹 أهم خطوة

    def get_queryset(self):
        if self.request.user.is_anonymous:
            return Alert.objects.none()  # هيرجع فاضي بدل ما يكسر
        return Alert.objects.filter(user=self.request.user).order_by('-created_at')

    def perform_create(self, serializer):
        # تحديد المستخدم تلقائيًا عند إنشاء تنبيه
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        alert = self.get_object()
        alert.read = True
        alert.save()
        return Response({"detail": "Alert marked as read"})


class HospitalAlertViewSet(viewsets.ModelViewSet):
    queryset = AlertHospital.objects.all()
    serializer_class = AlertHospitalSerializer

    def get_queryset(self):
        return AlertHospital.objects.all().order_by('-created_at')

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        alert = self.get_object()
        alert.read = True
        alert.save()
        return Response({"detail": "Alert marked as read"})


class AllergyViewSet(viewsets.ModelViewSet):
    queryset = Allergy.objects.all()
    serializer_class = AllergySerializer


class MedicineViewSet(viewsets.ModelViewSet):
    queryset = Medicine.objects.all()
    serializer_class = MedicineSerializer

    def get_queryset(self):
        user_id = self.request.query_params.get('user')
        qs = super().get_queryset()
        if user_id:
            qs = qs.filter(user_id=user_id)
        return qs


class HospitalTokenAuthentication(BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.headers.get("Authorization")

        if not auth_header or not auth_header.startswith("Bearer "):
            return None

        token_key = auth_header.split(" ")[1]

        try:
            token = HospitalToken.objects.get(key=token_key)
        except HospitalToken.DoesNotExist:
            raise exceptions.AuthenticationFailed("توكن المستشفى غير صالح")

        return (token.hospital, token)


class ChangeHospitalPasswordView(APIView):
    authentication_classes = [HospitalTokenAuthentication]

    def post(self, request):

        serializer = ChangePasswordSerializer(data=request.data)
        if serializer.is_valid():
            hospital = request.user
            old_pass = serializer.validated_data["old_password"]
            new_pass = serializer.validated_data["new_password"]

            if not hospital.check_password(old_pass):
                return Response(
                    {"error": "كلمة السر القديمة غير صحيحة"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            hospital.set_password(new_pass)
            hospital.save()
            return Response({"message": "تم تغيير كلمة السر بنجاح"})

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PatientSearchViewSet(viewsets.ReadOnlyModelViewSet):
    def get_queryset(self):
        return User.objects.filter(role='patient')

    serializer_class = UserSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        search = request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(medical_record_number__icontains=search)
            )

        organ = request.query_params.get('organ')
        if organ and organ.lower() != 'all':
            queryset = queryset.filter(patient_profile__organ_needed__icontains=organ)

        status = request.query_params.get('status')
        if status and status.lower() != 'all':
            queryset = queryset.filter(status=status)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class DonorSearchViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = User.objects.filter(role='donor')
    serializer_class = UserSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        # فلترة بالبحث (input)
        search = request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(medical_record_number__icontains=search)
            )

        organ = request.query_params.get('organ')
        if organ and organ.lower() != 'all':
            queryset = queryset.filter(donor_profile__organ_available__icontains=organ)

        status = request.query_params.get('status')
        if status and status.lower() != 'all':
            queryset = queryset.filter(status=status)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
