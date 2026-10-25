# One target group, on the web container's port 3000.
#
# The API is not a separate target because the browser reaches it same-origin:
# Next.js rewrites /api/* to the api container on 127.0.0.1:8000, stripping the
# prefix. That keeps NEXT_PUBLIC_API_URL a relative "/api", which means no CORS
# and no need to know the ALB hostname at image build time.
#
# Path-based routing to a second target group is not possible without a backend
# change, because the API serves /health, /assets and /dashboard at the root and
# those collide with the frontend's own page routes.

resource "aws_lb" "main" {
  name               = var.name
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id
}

resource "aws_lb_target_group" "web" {
  name        = "${var.name}-web"
  port        = 3000
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = aws_vpc.main.id

  # Shorter than the 300s default so teardown and redeploys are not held up
  # draining connections a lab environment does not have.
  deregistration_delay = 30

  # Reaches the API through the rewrite, so it proves the whole chain. The
  # endpoint is deliberately dependency-free — a database blip must not take
  # the service out of the load balancer.
  health_check {
    path                = "/api/health"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 30
    timeout             = 5
    matcher             = "200"
  }

  lifecycle {
    create_before_destroy = true
  }
}

# HTTP only. Adding HTTPS needs a domain and an ACM certificate, and no domain
# has been chosen (docs/REQUIRES_YOUR_INPUT.md). Until then Cognito tokens cross
# the network in cleartext, so use test accounts and no real personal data.
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.web.arn
  }
}
