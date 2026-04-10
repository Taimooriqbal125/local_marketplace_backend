"""
ServiceListing Routes — API endpoints for Service Listings.
"""

import json
import uuid
from typing import Optional, Union

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.security import get_current_user, get_optional_current_user
from app.core.rate_limiter import (
    services_create_rate_limit,
    services_list_rate_limit,
    services_nearby_me_rate_limit,
)
from app.db.session import get_db
from app.models.user import User
from app.schemas.services_listing import (
    ServiceListingCreate,
    ServiceListingFilterParams,
    ServiceListingMeListResponse,
    ServiceListingPublicListResponse,
    ServiceListingProfileSummaryListResponse,
    ServiceListingNearbyFilterParams,
    ServiceListingNearbyListResponse,
    ServiceListingResponse,
    ServiceListingDetailResponse,
    ServiceListingUpdate,
)
from app.services.listing_media_service import ListingMediaService
from app.services.service_listing_service import ServiceListingService

router = APIRouter(
    prefix="/services",
    tags=["Services"],
)


def _parse_service_listing_form(
    title: Optional[str] = Form(default=None),
    description: Optional[str] = Form(default=None),
    price_type: Optional[str] = Form(default=None, alias="priceType"),
    price_amount: Optional[float] = Form(default=None, alias="priceAmount"),
    is_negotiable: Optional[bool] = Form(default=None, alias="isNegotiable"),
    service_location: Optional[str] = Form(default=None, alias="serviceLocation"),
    service_radius_km: Optional[float] = Form(default=None, alias="serviceRadiusKm"),
    category_id: Optional[uuid.UUID] = Form(default=None, alias="categoryId"),
    city_id: Optional[uuid.UUID] = Form(default=None, alias="cityId"),
    status_value: Optional[str] = Form(default=None, alias="status"),
    service_point: Optional[str] = Form(default=None, alias="servicePoint"),
    service_point_latitude: Optional[float] = Form(default=None, alias="servicePoint.latitude"),
    service_point_longitude: Optional[float] = Form(default=None, alias="servicePoint.longitude"),
    latitude: Optional[float] = Form(default=None, alias="latitude"),
    longitude: Optional[float] = Form(default=None, alias="longitude"),
) -> Optional[ServiceListingCreate]:
    """
    Parse multipart/form-data into ServiceListingCreate.
    Accepts servicePoint as JSON string, e.g. {"latitude": 24.8, "longitude": 67.0}.
    Returns None when no form listing fields are provided.
    """
    has_form_payload = any(
        value is not None
        for value in (
            title,
            description,
            price_type,
            price_amount,
            is_negotiable,
            service_location,
            service_radius_km,
            category_id,
            city_id,
            status_value,
            service_point,
            service_point_latitude,
            service_point_longitude,
            latitude,
            longitude,
        )
    )
    if not has_form_payload:
        return None

    parsed_service_point = None
    lat_value = service_point_latitude if service_point_latitude is not None else latitude
    lon_value = service_point_longitude if service_point_longitude is not None else longitude

    if lat_value is not None or lon_value is not None:
        if lat_value is None or lon_value is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Both latitude and longitude are required when using form coordinate fields.",
            )
        parsed_service_point = {"latitude": lat_value, "longitude": lon_value}
    elif service_point is not None and str(service_point).strip() != "":
        try:
            parsed_service_point = json.loads(service_point)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="servicePoint must be a valid JSON object string.",
            ) from exc

    try:
        return ServiceListingCreate.model_validate(
            {
                "title": title,
                "description": description,
                "priceType": price_type if price_type is not None else "fixed",
                "priceAmount": price_amount,
                "isNegotiable": is_negotiable if is_negotiable is not None else False,
                "serviceLocation": service_location,
                "serviceRadiusKm": service_radius_km,
                "categoryId": category_id,
                "cityId": city_id,
                "status": status_value if status_value is not None else "draft",
                "servicePoint": parsed_service_point,
            }
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=jsonable_encoder(exc.errors()),
        ) from exc


@router.get(
    "/nearby/me",
    response_model=ServiceListingNearbyListResponse,
    dependencies=[Depends(services_nearby_me_rate_limit)],
)
def get_nearby_listings_from_profile(
    radius_km: float = Query(10.0, ge=0.1, le=100.0, description="Search radius in km"),
    category: Optional[uuid.UUID] = Query(
        default=None,
        description="Filter by category ID",
    ),
    filters: ServiceListingNearbyFilterParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Find nearby services using your saved profile location.
    No need to send lat/lng — reads from your last_location_point automatically.
    Update your location first via PATCH /profile/me/location.
    """
    return ServiceListingService(db).search_nearby_from_profile(
        user_id=current_user.id,
        db=db,
        radius_km=radius_km,
        status=filters.status,
        is_negotiable=filters.is_negotiable,
        price_type=filters.price_type,
        category_id=category if category is not None else filters.category_id,
        top_selling=filters.top_selling,
        top_rating=filters.top_rating,
        page=filters.page,
        page_size=filters.page_size,
    )


@router.get("/nearby", response_model=ServiceListingNearbyListResponse)
def get_nearby_listings(
    latitude: float = Query(..., ge=-90, le=90, description="Your current latitude"),
    longitude: float = Query(..., ge=-180, le=180, description="Your current longitude"),
    radius_km: float = Query(10.0, ge=0.1, le=100.0, description="Search radius in km"),
    filters: ServiceListingNearbyFilterParams = Depends(),
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """
    Find active service listings near a given location.
    Returns listings whose coverage radius overlaps your position, sorted closest-first.
    """
    return ServiceListingService(db).search_nearby(
        latitude=latitude,
        longitude=longitude,
        radius_km=radius_km,
        status=filters.status,
        is_negotiable=filters.is_negotiable,
        price_type=filters.price_type,
        category_id=filters.category_id,
        exclude_seller_id=current_user.id if current_user is not None else None,
        top_selling=filters.top_selling,
        top_rating=filters.top_rating,
        page=filters.page,
        page_size=filters.page_size,
    )


@router.get(
    "/",
    dependencies=[Depends(services_list_rate_limit)],
    response_model=Union[
        ServiceListingPublicListResponse,
        ServiceListingProfileSummaryListResponse,
    ],
)
def list_listings(
    category: Optional[uuid.UUID] = Query(
        default=None,
        description="Filter by category ID",
    ),
    profile_id: Optional[uuid.UUID] = Query(
        default=None,
        alias="profileId",
        description="Filter by profile/user ID",
    ),
    profile_id_legacy: Optional[uuid.UUID] = Query(
        default=None,
        alias="profileid",
        include_in_schema=False,
    ),
    filters: ServiceListingFilterParams = Depends(),
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """
    Browse service listings with optional filters.
    By default, only 'active' listings are returned.

    **Filter examples**
    - `?isNegotiable=true` — only negotiable listings
    - `?priceType=fixed` — only fixed-price listings
    - `?minPrice=10&maxPrice=100` — price range
    - `?search=plumbing` — keyword in title or description
    - `?categoryId=UUID` — specific category
    - `?status=paused` — listings by status
    - `?profileId=UUID` — lightweight cards for one profile/user (name, imageUrl, price + total)
    - `?topSelling=true` — sort by top selling sellers
    - `?topRating=true` — sort by top rated sellers
    """
    resolved_profile_id = (
        profile_id
        if profile_id is not None
        else profile_id_legacy
        if profile_id_legacy is not None
        else filters.profile_id
    )

    if resolved_profile_id is not None:
        return ServiceListingService(db).list_profile_listing_summaries(
            profile_id=resolved_profile_id,
            status=filters.status,
            category_id=category if category is not None else filters.category_id,
            city_id=filters.city_id,
            is_negotiable=filters.is_negotiable,
            price_type=filters.price_type,
            min_price=filters.min_price,
            max_price=filters.max_price,
            search=filters.search,
            top_selling=filters.top_selling,
            top_rating=filters.top_rating,
            city_slug=filters.city_slug,
            category_slug=filters.category_slug,
            exclude_seller_id=current_user.id if current_user is not None else None,
            page=filters.page,
            page_size=filters.page_size,
        )

    return ServiceListingService(db).list_listings(
        status=filters.status,
        category_id=category if category is not None else filters.category_id,
        city_id=filters.city_id,
        # Home feed should never be narrowed by sellerId.
        # profileId branch above handles profile-specific listing views.
        seller_id=None,
        is_negotiable=filters.is_negotiable,
        price_type=filters.price_type,
        min_price=filters.min_price,
        max_price=filters.max_price,
        search=filters.search,
        top_selling=filters.top_selling,
        top_rating=filters.top_rating,
        city_slug=filters.city_slug,
        category_slug=filters.category_slug,
        exclude_seller_id=current_user.id if current_user is not None else None,
        page=filters.page,
        page_size=filters.page_size,
    )


@router.get("/me", response_model=ServiceListingMeListResponse)
def list_my_listings(
    filters: ServiceListingFilterParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieve listings belonging to the authenticated user.
    Includes 'active' listings by default. Use `?status=` to filter.

    **Filter examples**
    - `?status=active` — only your active listings
    - `?status=draft` — only your drafts
    - `?isNegotiable=true` — your negotiable listings
    - `?search=logo` — keyword search in your listings
    """
    return ServiceListingService(db).list_my_listings(
        seller_id=current_user.id,
        status=filters.status,
        category_id=filters.category_id,
        is_negotiable=filters.is_negotiable,
        price_type=filters.price_type,
        min_price=filters.min_price,
        max_price=filters.max_price,
        search=filters.search,
        top_selling=filters.top_selling,
        top_rating=filters.top_rating,
        city_slug=filters.city_slug,
        category_slug=filters.category_slug,
        page=filters.page,
        page_size=filters.page_size,
    )


@router.get("/{listing_id}", response_model=ServiceListingDetailResponse)
def get_listing(
    listing_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """
    Get detailed information for a single service listing.
    """
    return ServiceListingService(db).get_listing(listing_id)


@router.post(
    "/",
    response_model=ServiceListingResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(services_create_rate_limit)],
)
async def create_listing(
    listing_in: Optional[ServiceListingCreate] = Body(default=None),
    listing_form: Optional[ServiceListingCreate] = Depends(_parse_service_listing_form),
    images: Optional[list[UploadFile]] = File(
        default=None,
        description="Optional listing images. Use multipart/form-data with field name 'images'.",
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a new service listing.

    Supports two input modes:
    1) application/json body using ServiceListingCreate.
    2) multipart/form-data using listing fields + optional 'images' files.

    If images are provided, they are uploaded to Cloudinary and stored in
    listing_media in the same request flow.
    """
    payload = listing_in if listing_in is not None else listing_form
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide listing data as JSON body or multipart/form-data fields.",
        )

    created_listing = ServiceListingService(db).create_listing(payload, seller_id=current_user.id)

    if images:
        media_service = ListingMediaService(db)
        for sort_order, image in enumerate(images):
            if image is None or not getattr(image, "filename", None):
                continue
            await media_service.upload_and_add_media(
                listing_id=created_listing.id,
                file=image,
                sort_order=sort_order,
                current_seller_id=current_user.id,
            )

    return created_listing


@router.patch("/{listing_id}", response_model=ServiceListingResponse)
def update_listing(
    listing_id: uuid.UUID,
    listing_in: ServiceListingUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update an existing listing.
    Only the owner of the listing can update it.
    """
    return ServiceListingService(db).update_listing(
        listing_id=listing_id,
        obj_in=listing_in,
        current_seller_id=current_user.id,
        is_admin=current_user.is_admin,
    )


@router.delete("/{listing_id}", status_code=status.HTTP_200_OK)
def delete_listing(
    listing_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete a service listing permanently.
    Admin can delete any listing; Sellers can delete only their own.
    """
    ServiceListingService(db).delete_listing(
        listing_id=listing_id, 
        current_user_id=current_user.id,
        is_admin=current_user.is_admin
    )
    return {"message": "Service listing deleted successfully."}
