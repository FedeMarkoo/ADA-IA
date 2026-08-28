package com.ada.conversation.application.dto;

public sealed interface MessageExecutionState
    permits MessageExecutionState.Received,
        MessageExecutionState.FilteringCommand,
        MessageExecutionState.SelectingContext,
        MessageExecutionState.CreatingContext,
        MessageExecutionState.InvokingModel,
        MessageExecutionState.InvokingTool,
        MessageExecutionState.Completed,
        MessageExecutionState.Failed {
  String code();

  String detail();

  record Received() implements MessageExecutionState {
    public String code() {
      return "received";
    }

    public String detail() {
      return null;
    }
  }

  record FilteringCommand() implements MessageExecutionState {
    public String code() {
      return "filtering_command";
    }

    public String detail() {
      return null;
    }
  }

  record CreatingContext() implements MessageExecutionState {
    public String code() {
      return "creating_context";
    }

    public String detail() {
      return null;
    }
  }

  record SelectingContext() implements MessageExecutionState {
    public String code() {
      return "selecting_context";
    }

    public String detail() {
      return null;
    }
  }

  record InvokingModel(String model) implements MessageExecutionState {
    public String code() {
      return "invoking_model";
    }

    public String detail() {
      return model;
    }
  }

  record InvokingTool(String tool) implements MessageExecutionState {
    public String code() {
      return "invoking_tool";
    }

    public String detail() {
      return tool;
    }
  }

  record Completed() implements MessageExecutionState {
    public String code() {
      return "completed";
    }

    public String detail() {
      return null;
    }
  }

  record Failed(String reason) implements MessageExecutionState {
    public String code() {
      return "failed";
    }

    public String detail() {
      return reason;
    }
  }
}
