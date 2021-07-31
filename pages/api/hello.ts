// Next.js API route support: https://nextjs.org/docs/api-routes/introduction
import type { NextApiRequest, NextApiResponse } from 'next'
import { RabbitMQ } from '../../lib/rabbitmq.service';

type Data = {
  name: string
}

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse<Data>
) {
  RabbitMQ.sendToQueue("John Doe");
  res.status(200).json({ name: 'John Doe' })
}
