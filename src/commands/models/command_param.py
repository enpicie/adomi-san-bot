from dataclasses import dataclass
from typing import Optional, List

from discord import AppCommandOptionType

@dataclass
class ParamChoice:
    name: str
    value: str

@dataclass
class CommandParam:
  name: str
  description: str
  param_type: AppCommandOptionType
  required: bool
  choices: Optional[List[ParamChoice]]

  def to_dict(self) -> dict:
      param_dict = {
          "name": self.name,
          "description": self.description or "No description",
          "type": self.param_type.value,
          "required": self.required,
      }
      if self.choices:
          param_dict["choices"] = [{"name": choice.name, "value": choice.value} for choice in self.choices]
      return param_dict
