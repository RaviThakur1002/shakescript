from supabase import create_client, Client
from app.core.config import settings
from typing import Dict, List, Any
import json


class DBService:
    def __init__(self):
        self.supabase: Client = create_client(
            settings.SUPABASE_URL, settings.SUPABASE_KEY
        )

    def get_all_stories(self) -> List[Dict[str, Any]]:
        result = self.supabase.table("stories").select("id, title").execute()
        return result.data if result.data else []

    def get_story_info(self, story_id: int) -> Dict:
        story_result = self.supabase.table("stories").select("*").eq("id", story_id).execute()
        
        if not story_result.data:
            return {"error": "Story not found"}
        
        story_row = story_result.data[0]

        episodes_result = (
            self.supabase.table("episodes")
            .select("id, episode_number, title, content, summary , emotional_state")
            .eq("story_id", story_id)
            .order("episode_number")
            .execute()
        )

        episodes_list = [
            {
                "id": ep["id"],
                "number": ep["episode_number"],
                "title": ep["title"],
                "content": ep["content"],
                "summary": ep["summary"],
                "emotional_state": ep["emotional_state"],
            }
            for ep in episodes_result.data
        ]

        characters_result = self.supabase.table("characters").select("*").eq("story_id", story_id).execute()
        characters = [
            {
                "Name": char["name"],
                "Role": char["role"],
                "Description": char["description"],
                "Relationship": json.loads(char["relationship"] or "{}"),
                "role_active": char["is_active"],
            }
            for char in characters_result.data
        ]

        return {
            "id": story_row["id"],
            "title": story_row["title"],
            "setting": json.loads(story_row["setting"] or "[]"),
            "key_events": json.loads(story_row["key_events"] or "[]"),
            "special_instructions": story_row["special_instructions"],
            "story_outline": json.loads(story_row["story_outline"] or "{}"),
            "current_episode": story_row["current_episode"],
            "episodes": episodes_list,
            "characters": characters, 
            "summary": story_row.get("summary"),
            "num_episodes": story_row["num_episodes"],
        }

    def store_story_metadata(self, metadata: Dict, num_episodes: int) -> int:
        setting = json.dumps(metadata.get("Settings", []))
        story_outline = json.dumps(metadata.get("Story Outline", {}))
        special_instructions = metadata.get("Special Instructions", "")
        
        result = (
            self.supabase.table("stories")
            .insert(
                {
                    "title": metadata.get("Title", "Untitled Story"),
                    "setting": setting,
                    "key_events": json.dumps([]),
                    "special_instructions": special_instructions,
                    "story_outline": story_outline,
                    "current_episode": 1,
                    "num_episodes": num_episodes,
                }
            )
            .execute()
        )

        if not result.data:
            raise Exception("Failed to insert story metadata into Supabase")

        story_id = result.data[0]["id"]
        characters = metadata.get("Characters", [])

        if not isinstance(characters, list):
            characters = []

        character_data_list = [
            {
                "story_id": story_id,
                "name": char["Name"],
                "role": char["Role"],
                "description": char["Description"],
                "relationship": json.dumps(char["Relationship"]),
                "emotional_state":char["Emotional_State"],
                "is_active": True,
            }
            for char in characters
        ]

        if character_data_list:
            self.supabase.table("characters").insert(character_data_list).execute()

        return story_id

    def store_episode(self, story_id: int, episode_data: Dict, current_episode: int) -> int:
        episode_result = (
            self.supabase.table("episodes")
            .upsert(
                {
                    "story_id": story_id,
                    "episode_number": current_episode,
                    "title": episode_data.get("episode_title", f"Episode {current_episode}"),
                    "content": episode_data.get("episode_content", ""),
                    "summary": episode_data.get("episode_summary", ""),
                    "emotional_state": episode_data.get("episode_emotional_state", "neutral"),
                },
                on_conflict="story_id,episode_number",
            )
            .execute()
        )

        if not episode_result.data:
            raise Exception("Failed to upsert episode into Supabase")

        episode_id = episode_result.data[0]["id"]

        character_data = episode_data.get("characters_featured", [])

        if isinstance(character_data, str):
            try:
                character_data = json.loads(character_data)
            except json.JSONDecodeError:
                character_data = []
        
        if not isinstance(character_data, list):
            character_data = []

        character_data_list = [
            {
                "story_id": story_id,
                "name": char.get("Name"),
                "role": char.get("Role", "supporting"),
                "description": char.get("Description", ""),
                "relationship": json.dumps(char.get("Relationship", {})),
                "emotional_state": char.get("Emotional_State", "neutral"),
                "is_active": char.get("role_active", True),
            }
            for char in character_data
        ]

        if character_data_list:
            self.supabase.table("characters").upsert(character_data_list, on_conflict="story_id,name").execute()

        story_data = self.supabase.table("stories").select("key_events").eq("id", story_id).execute().data
        current_key_events = json.loads(story_data[0]["key_events"] or "[]") if story_data else []
        new_key_events = episode_data.get("Key Events", [])

        updated_key_events = list(set(current_key_events + new_key_events))

        self.supabase.table("stories").update(
            {
                "current_episode": current_episode + 1,
                "setting": json.dumps(episode_data.get("Settings", [])),
                "key_events": json.dumps(updated_key_events),
            }
        ).eq("id", story_id).execute()

        return episode_id

