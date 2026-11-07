"use client";

import { Container } from "@/components/Container";
import { Mail, MapPin, Send, CheckCircle } from "lucide-react";
import { useState } from "react";

export default function ContactPage() {
  const [submitted, setSubmitted] = useState(false);
  const [formData, setFormData] = useState({ name: "", email: "", subject: "", message: "" });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (formData.email && formData.message) {
      setSubmitted(true);
    }
  };

  return (
    <Container className="py-12 max-w-4xl space-y-10">
      <div className="border-b border-border pb-6 space-y-2">
        <span className="text-xs font-bold uppercase tracking-widest text-secondary">
          Inquiries & Feedback
        </span>
        <h1 className="text-3xl md:text-4xl font-serif font-bold text-foreground">
          Contact Editorial Desk
        </h1>
        <p className="text-base text-muted leading-relaxed font-sans">
          Have an editorial inquiry, discovery correction, or publisher attribution request? Get in touch with our team.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        <div className="space-y-6 md:col-span-1">
          <div className="space-y-2">
            <h3 className="text-xs font-bold uppercase tracking-wider text-secondary flex items-center space-x-1.5">
              <Mail className="w-4 h-4" />
              <span>Editorial Inquiries</span>
            </h3>
            <p className="text-sm font-semibold text-foreground">editorial@metroscope.news</p>
            <p className="text-xs text-muted">For corrections and story discovery feedback.</p>
          </div>

          <div className="space-y-2">
            <h3 className="text-xs font-bold uppercase tracking-wider text-secondary flex items-center space-x-1.5">
              <MapPin className="w-4 h-4" />
              <span>Publisher Relations</span>
            </h3>
            <p className="text-sm font-semibold text-foreground">publishers@metroscope.news</p>
            <p className="text-xs text-muted">Syndication, indexing, and copyright notices.</p>
          </div>
        </div>

        <div className="md:col-span-2 border border-border p-6 rounded-lg bg-surface-lowest">
          {submitted ? (
            <div className="text-center py-10 space-y-3">
              <CheckCircle className="w-10 h-10 text-secondary mx-auto" />
              <h3 className="text-xl font-serif font-bold text-foreground">Message Transmitted</h3>
              <p className="text-xs text-muted max-w-md mx-auto">
                Thank you for contacting the MetroScope team. Our editorial staff will review your message promptly.
              </p>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4 text-xs">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-1">
                  <label htmlFor="name" className="font-semibold text-foreground">Your Name</label>
                  <input
                    id="name"
                    type="text"
                    required
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    className="w-full p-2.5 rounded border border-border bg-surface text-foreground focus:outline-none focus:border-secondary"
                    placeholder="Full name"
                  />
                </div>
                <div className="space-y-1">
                  <label htmlFor="email" className="font-semibold text-foreground">Email Address</label>
                  <input
                    id="email"
                    type="email"
                    required
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    className="w-full p-2.5 rounded border border-border bg-surface text-foreground focus:outline-none focus:border-secondary"
                    placeholder="name@organization.com"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <label htmlFor="subject" className="font-semibold text-foreground">Subject / Department</label>
                <input
                  id="subject"
                  type="text"
                  required
                  value={formData.subject}
                  onChange={(e) => setFormData({ ...formData, subject: e.target.value })}
                  className="w-full p-2.5 rounded border border-border bg-surface text-foreground focus:outline-none focus:border-secondary"
                  placeholder="Attribution, Correction, or General Inquiry"
                />
              </div>

              <div className="space-y-1">
                <label htmlFor="message" className="font-semibold text-foreground">Message</label>
                <textarea
                  id="message"
                  rows={5}
                  required
                  value={formData.message}
                  onChange={(e) => setFormData({ ...formData, message: e.target.value })}
                  className="w-full p-2.5 rounded border border-border bg-surface text-foreground focus:outline-none focus:border-secondary"
                  placeholder="Provide context, story URLs, or details..."
                />
              </div>

              <button
                type="submit"
                className="inline-flex items-center space-x-2 px-6 py-2.5 rounded bg-secondary text-white font-bold uppercase tracking-wider hover:bg-secondary/90 transition-colors"
              >
                <Send className="w-3.5 h-3.5" />
                <span>Submit Transmission</span>
              </button>
            </form>
          )}
        </div>
      </div>
    </Container>
  );
}
