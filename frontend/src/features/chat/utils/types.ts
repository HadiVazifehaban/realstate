export type Message = {
  id: string;
  sequence: number;
  senderSubject: string;
  senderName: string;
  clientMessageId: string;
  body: string;
  createdAt: string;
};

export type ConversationMember = {
  subject: string;
  displayName: string;
};

export type Conversation = {
  id: string;
  title: string;
  createdBySubject: string;
  createdAt: string;
  members: ConversationMember[];
  lastMessage: Message | null;
};
