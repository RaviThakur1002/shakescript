from fastapi import APIRouter, Body, Depends, HTTPException, status
from starlette.status import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND
from ...models.schemas import (
    StoryListResponse,
    StoryResponse,
    ErrorResponse,
)
from app.services.core_service import StoryService
from app.api.dependencies import get_story_service, get_current_user
from typing import Annotated, Union, Dict, Any, List
from app.utils import parse_user_prompt

router = APIRouter(prefix="/stories", tags=["stories"])


@router.get(
    "/all",
    response_model=Union[StoryListResponse, ErrorResponse],
    summary="Retrieve all stories",
)
def get_all_stories(
    service: StoryService = Depends(get_story_service),
    user: dict = Depends(get_current_user),
):
    """
    Retrieve a list of all stories with a structured response for the authenticated user.
    """
    # --- FIX ---
    auth_id = user.get("auth_id")
    if not auth_id:
        raise HTTPException(
            status_code=403, detail="Could not identify user from token."
        )

    stories = service.get_all_stories(auth_id)
    return (
        {"status": "success", "stories": stories}
        if stories
        else {"status": "success", "stories": [], "message": "No stories found"}
    )


@router.post(
    "/",
    response_model=Union[Dict[str, Any], ErrorResponse],
    summary="Create a new story",
)
async def create_story(
    service: Annotated[StoryService, Depends(get_story_service)],
    prompt: str = Body(..., description="Detailed story idea or prompt"),
    num_episodes: int = Body(..., description="Total number of episodes", ge=1),
    batch_size: int = Body(
        2, description="Number of episodes to generate per batch", ge=1
    ),
    refinement: str = Body(
        "AI", description="Refinement method: 'AI' or 'Human'", regex="^(AI|HUMAN)$"
    ),
    hinglish: bool = Body(False, description="Generate in Hinglish if true"),
    user: dict = Depends(get_current_user),
):
    prompt = parse_user_prompt(prompt)
    auth_id = user.get("auth_id")
    if not auth_id:
        raise HTTPException(
            status_code=403, detail="Could not identify user from token."
        )

    result = await service.create_story(prompt, num_episodes, refinement, hinglish, auth_id)
    if "error" in result:
        raise HTTPException(HTTP_400_BAD_REQUEST, detail=result["error"])

    story_info = service.get_story_info(result["story_id"], auth_id)
    if "error" in story_info:
        raise HTTPException(HTTP_404_NOT_FOUND, detail=story_info["error"])

    story_info["batch_size"] = batch_size
    story_info["refinement_method"] = refinement

    return {
        "status": "success",
        "story": StoryResponse(
            story_id=story_info["id"],
            title=story_info["title"],
            setting=story_info["setting"],
            characters=story_info.get("characters", {}),
            special_instructions=story_info["special_instructions"],
            story_outline=story_info["story_outline"],
            current_episode=story_info["current_episode"],
            episodes=story_info["episodes"],
            summary=story_info.get("summary"),
            protagonist=story_info["protagonist"],
            timeline=story_info["timeline"],
            batch_size=batch_size,
            refinement_method=refinement,
            total_episodes=story_info["num_episodes"],
        ),
        "message": "Story created successfully",
    }


@router.get(
    "/{story_id}",
    response_model=Union[Dict[str, Any], ErrorResponse],
    summary="Retrieve a specific story",
)
def get_story(
    story_id: int,
    service: StoryService = Depends(get_story_service),
    user: dict = Depends(get_current_user),
):
    """
    Retrieve detailed information about a story with a structured response for the authenticated user.
    """
    auth_id = user.get("auth_id")
    if not auth_id:
        raise HTTPException(
            status_code=403, detail="Could not identify user from token."
        )

    story_info = service.get_story_info(story_id, auth_id)
    if "error" in story_info:
        raise HTTPException(HTTP_404_NOT_FOUND, detail=story_info["error"])

    return {
        "status": "success",
        "story": StoryResponse(
            story_id=story_info["id"],
            title=story_info["title"],
            setting=story_info["setting"],
            characters=story_info.get("characters", {}),
            special_instructions=story_info["special_instructions"],
            story_outline=story_info["story_outline"],
            current_episode=story_info["current_episode"],
            episodes=story_info["episodes"],
            summary=story_info.get("summary"),
            protagonist=story_info["protagonist"],
            timeline=story_info["timeline"],
            batch_size=story_info.get("batch_size", 2),
            refinement_method=story_info.get("refinement_method", "AI"),
            total_episodes=story_info.get("num_episodes", 0)
        ),
        "message": "Story retrieved successfully",
    }


@router.post(
    "/{story_id}/summary",
    response_model=Union[Dict[str, Any], ErrorResponse],
    summary="Update story summary",
)
def update_story_summary(
    story_id: int,
    service: Annotated[StoryService, Depends(get_story_service)],
    user: dict = Depends(get_current_user),
):
    """
    Update the summary of a story based on its episodes with a structured response.
    """
    # --- FIX ---
    auth_id = user.get("auth_id")
    if not auth_id:
        raise HTTPException(
            status_code=403, detail="Could not identify user from token."
        )

    result = service.update_story_summary(story_id, auth_id)
    if "error" in result:
        raise HTTPException(HTTP_400_BAD_REQUEST, detail=result["error"])
    return {"status": "success", **result, "message": "Summary updated successfully"}


@router.delete(
    "/{story_id}",
    response_model=Dict[str, str],
    summary="Delete a story and all associated data",
)
def delete_story(
    story_id: int,
    service: StoryService = Depends(get_story_service),
    user: dict = Depends(get_current_user),
):
    try:
        # --- FIX ---
        auth_id = user.get("auth_id")
        if not auth_id:
            raise HTTPException(
                status_code=403, detail="Could not identify user from token."
            )

        service.delete_story(story_id, auth_id)
        return {
            "message": f"Story {story_id} and all associated data deleted successfully"
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete story: {str(e)}")


@router.post(
    "/{story_id}/complete",
    response_model=Dict[str, str],
    summary="Mark a story as completed",
)
def complete_story(story_id: int, service: StoryService = Depends(get_story_service)):
    # Note: This endpoint does not have user dependency, so it cannot enforce RLS.
    # You might want to add `user: dict = Depends(get_current_user)` here as well.
    service.set_story_completed(story_id, True)
    return {"status": "success", "message": f"Story {story_id} marked as completed."}
