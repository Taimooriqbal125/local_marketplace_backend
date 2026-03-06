# app/api/v1/endpoints/profiles.py

@router.post("/", status_code=status.HTTP_201_CREATED)  # 👈 POST - CREATE
async def create_profile(
    profile_data: str = Form(...),
    file: UploadFile = File(None),
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """
    CREATE profile - pehli baar profile bana rahe ho
    POST /api/v1/profiles
    """
    try:
        # Parse JSON
        data_dict = json.loads(profile_data)
        validated_data = ProfileUpdateData(**data_dict)
        
        # CHECK: Profile already exists?
        existing = db.query(Profile).filter(
            Profile.user_id == current_user.id
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Profile already exists! Use PATCH to update."
            )
        
        # Create NEW profile
        profile = Profile(
            user_id=current_user.id,
            name=validated_data.name,
            bio=validated_data.bio,
            latitude=validated_data.last_location_point.latitude,
            longitude=validated_data.last_location_point.longitude
        )
        
        # Handle image if provided
        if file:
            result = await cloudinary_service.upload_image(
                file=file,
                folder=f"profiles/{current_user.id}"
            )
            profile.image_url = result["url"]
            profile.image_public_id = result["public_id"]
        
        db.add(profile)
        db.commit()
        db.refresh(profile)
        
        return {
            "success": True,
            "message": "Profile created successfully",
            "data": profile
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/me")  # 👈 PATCH - UPDATE
async def update_profile(
    profile_data: str = Form(...),
    file: UploadFile = File(None),
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """
    UPDATE profile - mojoda profile update kar rahe ho
    PATCH /api/v1/profiles/me
    """
    try:
        # Parse JSON
        data_dict = json.loads(profile_data)
        validated_data = ProfileUpdateData(**data_dict)
        
        # FIND existing profile
        profile = db.query(Profile).filter(
            Profile.user_id == current_user.id
        ).first()
        
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profile not found! Use POST to create first."
            )
        
        # UPDATE existing fields
        profile.name = validated_data.name
        profile.bio = validated_data.bio
        profile.latitude = validated_data.last_location_point.latitude
        profile.longitude = validated_data.last_location_point.longitude
        
        # Handle new image
        if file:
            # Delete old image if exists
            if profile.image_public_id:
                await cloudinary_service.delete_image(profile.image_public_id)
            
            # Upload new image
            result = await cloudinary_service.upload_image(
                file=file,
                folder=f"profiles/{current_user.id}"
            )
            profile.image_url = result["url"]
            profile.image_public_id = result["public_id"]
        
        db.commit()
        db.refresh(profile)
        
        return {
            "success": True,
            "message": "Profile updated successfully",
            "data": profile
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))