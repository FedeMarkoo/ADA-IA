package com.ada.conversation.infrastructure.out.state;

import com.ada.conversation.application.MessageStateTracker; import com.ada.conversation.application.dto.MessageExecutionState; import java.util.concurrent.ConcurrentHashMap; import org.springframework.stereotype.Component;
@Component public class InMemoryMessageStateTracker implements MessageStateTracker { private final ConcurrentHashMap<String,MessageExecutionState> states=new ConcurrentHashMap<>(); public void update(String id,MessageExecutionState s){states.put(id,s);} public MessageExecutionState current(String id){return states.get(id);} }
