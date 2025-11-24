from typing import List, Optional
from pydantic import BaseModel, Field

class BrowserAction(BaseModel):
    action_type: str = Field(..., description="操作タイプ (例: goto, click, fill, screenshot)")
    selector: Optional[str] = Field(None, description="操作対象のセレクタ")
    value: Optional[str] = Field(None, description="入力値など")
    description: str = Field(..., description="このステップの説明")

class BrowserScenario(BaseModel):
    title: str
    steps: List[BrowserAction]
